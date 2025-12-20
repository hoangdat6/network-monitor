"""
Flow Processor - CICFlowMeter CSV to Kafka

Mục đích: 
- Đọc CSV từ CICFlowMeter 
- Normalize features về format CICIDS2017
- Stream to Kafka for real-time detection

Tại sao Kafka: 
- Decoupling giữa data collection và processing
- High throughput, fault tolerance
- Multiple consumers (DDoS detector, Web detector)

Cách khác:
- Direct processing: Không scalable, single point of failure
- File-based: Slow, không real-time
- Redis Streams: Ít mature hơn Kafka

Bản chất hoạt động:
1. Watch directory cho CSV files
2. Parse & validate CSV
3. Map columns to CICIDS2017 format  
4. Send to Kafka với JSON format
5. Remove processed files
"""

import os
import time
import json
import logging
import pandas as pd
import numpy as np
from kafka import KafkaProducer
from kafka.errors import KafkaError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Dict, List, Optional
import signal
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FlowProcessor:
    """
    Process CICFlowMeter CSV files and stream to Kafka
    """
    
    # Keep original CICFlowMeter column names (snake_case format)
    # No column mapping needed - maintain consistency with ML model features
    
    def __init__(self, 
                 input_dir: str = '/output',  # Đọc từ /output (shared volume với cicflowmeter)
                 kafka_servers: List[str] = ['kafka:9092'],
                 kafka_topic: str = 'network-flows',
                 batch_size: int = 1000,
                 filter_local_ips: bool = True,
                 max_retries: int = 3,
                 ip_filter_config_path: str = None):
        
        self.input_dir = input_dir
        self.kafka_topic = kafka_topic
        self.batch_size = batch_size
        self.processed_files = set()
        self.failed_files = {} 
        self.filter_local_ips = filter_local_ips
        self.max_retries = max_retries
        self.max_processed_cache = 10000  
        
        # Load IP filtering configuration from YAML
        self._load_ip_filter_config(ip_filter_config_path)
        
        # Initialize Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            batch_size=16384,
            linger_ms=100,
            compression_type='gzip',
            retries=3,
            acks='all'
        )
        
        logger.info(f"FlowProcessor initialized: {input_dir} -> {kafka_topic}")
        logger.info(f"IP Filtering: {self.filter_local_ips}, Config: {ip_filter_config_path or 'default'}")
    
    def _load_ip_filter_config(self, config_path: Optional[str] = None):
        """
        Load IP filtering configuration from YAML file
        Falls back to defaults if file not found
        """
        import yaml
        
        # Default config path
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), 
                'ip_filter_config.yaml'
            )
        
        # Default values (fallback)
        default_config = {
            'enabled': True,
            'local_ip_ranges': [
                '192.168.', '10.', '127.', '169.254.',
                '172.16.', '172.17.', '172.18.', '172.19.',
                '172.20.', '172.21.', '172.22.', '172.23.',
                '172.24.', '172.25.', '172.26.', '172.27.',
                '172.28.', '172.29.', '172.30.', '172.31.',
            ],
            'trusted_ips': [],
            'trusted_ip_prefixes': []
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                    logger.info(f"Loaded IP filter config from: {config_path}")
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                config = default_config
        except Exception as e:
            logger.error(f"Failed to load IP filter config: {e}, using defaults")
            config = default_config
        
        # Apply configuration
        self.filter_enabled = config.get('enabled', True)
        self.local_ip_ranges = config.get('local_ip_ranges', default_config['local_ip_ranges'])
        self.trusted_ips = config.get('trusted_ips', [])
        self.trusted_ip_prefixes = config.get('trusted_ip_prefixes', [])
        
        # Log loaded configuration
        logger.info(f"IP Filter Config:")
        logger.info(f"  - Enabled: {self.filter_enabled}")
        logger.info(f"  - Local IP ranges: {len(self.local_ip_ranges)} ranges")
        logger.info(f"  - Trusted IPs: {len(self.trusted_ips)} IPs")
        logger.info(f"  - Trusted prefixes: {len(self.trusted_ip_prefixes)} prefixes")
        
    def validate_csv(self, file_path: str) -> bool:
        """
        Validate CSV file format and content
        """
        try:
            # Check file size
            if os.path.getsize(file_path) == 0:
                logger.warning(f"Empty file: {file_path}")
                return False
            
            # Try to read first few lines
            df_sample = pd.read_csv(file_path, nrows=5)
            
            if len(df_sample) == 0:
                logger.warning(f"No data rows in: {file_path}")
                return False
            
            # Check for basic required columns (từ CICFlowMeter hoặc basic flow analysis)
            required_cols = ['src_ip', 'dst_ip', 'tot_fwd_pkts']
            missing_cols = [col for col in required_cols if col not in df_sample.columns]
            
            if missing_cols:
                logger.warning(f"Missing required columns {missing_cols} in: {file_path}")
                return False
                
            logger.debug(f"CSV validation passed: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"CSV validation failed for {file_path}: {e}")
            return False
    
    def should_filter_ip(self, ip: str) -> bool:
        """
        Check if IP should be filtered out (local, private, or trusted)
        Returns True if IP should be FILTERED (removed)
        """
        if pd.isna(ip) or not isinstance(ip, str):
            return True
        
        # Check local/private IPs
        if any(ip.startswith(prefix) for prefix in self.local_ip_ranges):
            return True
        
        # Check exact trusted IPs (DNS servers, etc.)
        if ip in self.trusted_ips:
            return True
        
        # Check trusted IP prefixes (Google, Cloudflare, etc.)
        if any(ip.startswith(prefix) for prefix in self.trusted_ip_prefixes):
            return True
        
        return False
    
    def filter_flows(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter flows - remove local IPs and trusted IPs (DNS, CDN, etc.)
        Only keep traffic from potentially malicious external sources
        """
        if not self.filter_local_ips:
            return df
        
        initial_count = len(df)
        
        # Tìm cột IP (có thể là 'src_ip' hoặc 'Src IP')
        src_ip_col = None
        for col in ['src_ip', 'Src IP', 'Source IP', 'src']:
            if col in df.columns:
                src_ip_col = col
                break
        
        if src_ip_col is None:
            logger.warning("No source IP column found, skipping IP filtering")
            return df
        
        # Lọc: chỉ giữ flows từ external IPs (không phải local và không phải trusted)
        df['should_keep'] = df[src_ip_col].apply(lambda ip: not self.should_filter_ip(ip))
        df_filtered = df[df['should_keep']].copy()
        df_filtered = df_filtered.drop(columns=['should_keep'])
        
        filtered_count = initial_count - len(df_filtered)
        if filtered_count > 0:
            logger.info(f"Filtered {filtered_count} flows (local/trusted IPs), kept {len(df_filtered)} external flows")
        
        return df_filtered
    
    def add_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add engineered features for improved model performance
        """
        df = df.copy()
        
        # Ensure required columns exist
        if 'tot_fwd_pkts' not in df.columns:
            df['tot_fwd_pkts'] = 0
        if 'tot_bwd_pkts' not in df.columns:
            df['tot_bwd_pkts'] = 0
        
        # 1. Total packets
        df['total_packets'] = df['tot_fwd_pkts'].fillna(0) + df['tot_bwd_pkts'].fillna(0)
        
        # 2. Total bytes
        fwd_bytes_col = 'totlen_fwd_pkts' if 'totlen_fwd_pkts' in df.columns else 'subflow_fwd_byts'
        bwd_bytes_col = 'totlen_bwd_pkts' if 'totlen_bwd_pkts' in df.columns else 'subflow_bwd_byts'
        
        df['total_fwd_bytes'] = df.get(fwd_bytes_col, pd.Series([0]*len(df))).fillna(0)
        df['total_bwd_bytes'] = df.get(bwd_bytes_col, pd.Series([0]*len(df))).fillna(0)
        df['total_bytes'] = df['total_fwd_bytes'] + df['total_bwd_bytes']
        
        # 3. Flow duration (ensure positive, add small epsilon to avoid division by zero)
        if 'flow_duration' in df.columns:
            df['flow_duration'] = pd.to_numeric(df['flow_duration'], errors='coerce').fillna(0).clip(lower=0) + 1e-6
        else:
            df['flow_duration'] = 1.0
        
        # 4. Derived rate features
        df['packet_rate'] = df['total_packets'] / df['flow_duration']
        df['byte_rate'] = df['total_bytes'] / df['flow_duration']
        df['mean_packet_size'] = (df['total_bytes'] / df['total_packets'].replace({0: np.nan})).fillna(0)
        df['fwd_ratio'] = (df['tot_fwd_pkts'] / df['total_packets'].replace({0: np.nan})).fillna(0)
        
        # 5. IAT range
        if 'flow_iat_max' in df.columns and 'flow_iat_min' in df.columns:
            df['iat_range'] = (pd.to_numeric(df['flow_iat_max'], errors='coerce').fillna(0) -
                              pd.to_numeric(df['flow_iat_min'], errors='coerce').fillna(0)).clip(lower=0)
        else:
            df['iat_range'] = 0.0
        
        # 6. Log transforms (to handle skewed distributions)
        df['log_packet_rate'] = np.log1p(df['packet_rate'].clip(lower=0))
        df['log_byte_rate'] = np.log1p(df['byte_rate'].clip(lower=0))
        df['log_total_bytes'] = np.log1p(df['total_bytes'].clip(lower=0))
        df['log_total_packets'] = np.log1p(df['total_packets'].clip(lower=0))
        
        return df
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize data (similar to LSTM preprocessing)
        """
        # Handle inf/nan values - deprecated option removed
        # pd.set_option('mode.use_inf_as_na', True)
        
        # Replace inf with NaN, then fill with 0
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna(0)
        
        # Ensure numeric columns are float
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        df[numeric_columns] = df[numeric_columns].astype('float64')
        
        return df
    
    def process_csv(self, file_path: str) -> int:
        """
        Process single CSV file and send to Kafka
        Returns number of flows processed
        """
        if file_path in self.processed_files:
            return 0
        
        # Check if file has exceeded retry limit
        if file_path in self.failed_files:
            if self.failed_files[file_path] >= self.max_retries:
                logger.error(f"File {file_path} exceeded {self.max_retries} retries, removing...")
                try:
                    os.remove(file_path)
                    self.processed_files.add(file_path)
                    del self.failed_files[file_path]
                except Exception as e:
                    logger.error(f"Failed to remove error file {file_path}: {e}")
                return 0
            
        if not self.validate_csv(file_path):
            # Increment retry count for failed validation
            self.failed_files[file_path] = self.failed_files.get(file_path, 0) + 1
            return 0
            
        try:
            logger.info(f"Processing CSV: {file_path}")
            
            # Read CSV
            df = pd.read_csv(file_path)
            
            # No column renaming - keep original CICFlowMeter names
            # Filter local IPs (chỉ giữ traffic từ bên ngoài)
            df = self.filter_flows(df)
            
            # Skip if no flows left after filtering
            if len(df) == 0:
                logger.info(f"No external flows found in {file_path}, skipping")
                self.processed_files.add(file_path)
                os.remove(file_path)
                return 0
            
            # Clean data
            df = self.clean_data(df)
            
            # Add derived features (feature engineering)
            df = self.add_derived_features(df)
            
            # Add metadata
            df['source_file'] = os.path.basename(file_path)
            df['processed_at'] = pd.Timestamp.now().isoformat()
            
            # Send to Kafka in batches (async for performance)
            flows_sent = 0
            futures = []  # Track futures for error handling
            
            for start_idx in range(0, len(df), self.batch_size):
                batch = df.iloc[start_idx:start_idx + self.batch_size]
                
                # Convert batch to dict list (faster than iterrows)
                batch_dicts = batch.to_dict('records')
                
                for flow_data in batch_dicts:
                    try:
                        # Send async (don't wait for confirmation)
                        future = self.producer.send(self.kafka_topic, flow_data)
                        futures.append(future)
                        flows_sent += 1
                        
                    except KafkaError as e:
                        logger.error(f"Failed to send flow to Kafka: {e}")
                        continue
                
                # Log progress every 1000 flows
                if flows_sent % 1000 == 0:
                    logger.info(f"Sent {flows_sent}/{len(df)} flows...")
            
            # Flush producer and wait for all messages
            logger.info(f"Flushing {len(futures)} messages to Kafka...")
            self.producer.flush(timeout=60)
            
            # Check for errors (quick check, don't block)
            errors = 0
            for future in futures:
                try:
                    future.get(timeout=0.001)  # Very quick check
                except Exception:
                    errors += 1
            
            if errors > 0:
                logger.warning(f"Failed to send {errors}/{flows_sent} flows")
            
            logger.info(f"Successfully processed {flows_sent} flows from {file_path}")
            
            # Mark as processed
            self.processed_files.add(file_path)
            
            # Prevent memory leak: clear old processed files cache if too large
            if len(self.processed_files) > self.max_processed_cache:
                logger.warning(f"Processed files cache exceeded {self.max_processed_cache}, clearing oldest 50%...")
                # Keep only recent half (FIFO-like behavior)
                self.processed_files = set(list(self.processed_files)[self.max_processed_cache // 2:])
            
            # Remove from failed files if it was there
            if file_path in self.failed_files:
                del self.failed_files[file_path]
            
            # Remove processed file
            os.remove(file_path)
            logger.debug(f"Removed processed file: {file_path}")
            
            return flows_sent
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            
            # Increment retry count
            self.failed_files[file_path] = self.failed_files.get(file_path, 0) + 1
            
            # Remove file if max retries exceeded
            if self.failed_files[file_path] >= self.max_retries:
                logger.error(f"Removing corrupted file after {self.max_retries} failed attempts: {file_path}")
                try:
                    os.remove(file_path)
                    self.processed_files.add(file_path)
                    del self.failed_files[file_path]
                except Exception as remove_error:
                    logger.error(f"Failed to remove corrupted file: {remove_error}")
            
            return 0
    
    def health_check(self) -> Dict:
        """
        Return health status
        """
        try:
            # Test Kafka connection
            metadata = self.producer.get_cluster_metadata(timeout=5)
            kafka_healthy = len(metadata.brokers) > 0
        except:
            kafka_healthy = False
            
        return {
            'status': 'healthy' if kafka_healthy else 'unhealthy',
            'kafka_connected': kafka_healthy,
            'input_directory': self.input_dir,
            'kafka_topic': self.kafka_topic,
            'processed_files_count': len(self.processed_files),
            'failed_files_count': len(self.failed_files),
            'pending_retries': list(self.failed_files.keys()) if self.failed_files else [],
            'timestamp': pd.Timestamp.now().isoformat()
        }

class CSVPoller:
    """
    Polling-based CSV file processor - checks for stable files
    """
    
    def __init__(self, processor: FlowProcessor, poll_interval: int = 5):
        self.processor = processor
        self.poll_interval = poll_interval
        self.file_sizes = {}  # Track file sizes to detect stability
        self.stability_threshold = 5  # File must be stable for 5 seconds
        
    def is_file_stable(self, file_path: str) -> bool:
        """Check if file size hasn't changed for stability_threshold seconds"""
        try:
            current_size = os.path.getsize(file_path)
            current_time = time.time()
            
            # Skip empty files
            if current_size == 0:
                return False
            
            if file_path not in self.file_sizes:
                # First time seeing this file
                self.file_sizes[file_path] = (current_size, current_time)
                return False
            
            last_size, last_check_time = self.file_sizes[file_path]
            
            if current_size != last_size:
                # Size changed, update and mark as unstable
                self.file_sizes[file_path] = (current_size, current_time)
                return False
            
            # Size hasn't changed, check if enough time has passed
            if (current_time - last_check_time) >= self.stability_threshold:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking file stability for {file_path}: {e}")
            return False
    
    def poll(self):
        """Poll directory for stable CSV files"""
        try:
            if not os.path.exists(self.processor.input_dir):
                return
            
            for filename in os.listdir(self.processor.input_dir):
                if not (filename.startswith('flows_') and filename.endswith('.csv')):
                    continue
                
                file_path = os.path.join(self.processor.input_dir, filename)
                
                # Skip if already processed
                if file_path in self.processor.processed_files:
                    # Clean up from tracking dict
                    if file_path in self.file_sizes:
                        del self.file_sizes[file_path]
                    continue
                
                # Check if file is stable
                if self.is_file_stable(file_path):
                    logger.info(f"Stable CSV file detected: {file_path}")
                    self.processor.process_csv(file_path)
                    # Clean up from tracking
                    if file_path in self.file_sizes:
                        del self.file_sizes[file_path]
                        
        except Exception as e:
            logger.error(f"Error during polling: {e}")

def main():
    """
    Main function - start the flow processor
    """
    # Configuration from environment
    input_dir = os.getenv('INPUT_DIR', '/output')  # Đọc CSV từ CICFlowMeter output
    kafka_servers = os.getenv('KAFKA_BROKERS', 'kafka:9092').split(',')  # Sử dụng KAFKA_BROKERS
    kafka_topic = os.getenv('KAFKA_TOPIC', 'network-flows')
    batch_size = int(os.getenv('BATCH_SIZE', '1000'))
    filter_local = os.getenv('FILTER_LOCAL_IPS', 'true').lower() == 'true'
    max_retries = int(os.getenv('MAX_FILE_RETRIES', '3'))
    ip_filter_config = os.getenv('IP_FILTER_CONFIG_PATH', None)  # Optional custom config path
    
    # Create processor
    processor = FlowProcessor(
        input_dir=input_dir,
        kafka_servers=kafka_servers,
        kafka_topic=kafka_topic,
        batch_size=batch_size,
        filter_local_ips=filter_local,
        max_retries=max_retries,
        ip_filter_config_path=ip_filter_config
    )
    
    # Process existing completed files (not health check files)
    if os.path.exists(input_dir):
        for filename in sorted(os.listdir(input_dir)):
            if filename.endswith('.csv') and filename.startswith('flows_'):
                file_path = os.path.join(input_dir, filename)
                # Only process if file is stable (not currently being written)
                if os.path.exists(file_path):
                    processor.process_csv(file_path)
    
    # Start file poller
    poller = CSVPoller(processor, poll_interval=5)
    
    logger.info(f"Flow processor started, polling: {input_dir} every {poller.poll_interval}s")
    
    # Graceful shutdown handler
    running = True
    def signal_handler(signum, frame):
        nonlocal running
        logger.info("Shutting down flow processor...")
        running = False
        processor.producer.close()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while running:
            poller.poll()
            time.sleep(poller.poll_interval)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()