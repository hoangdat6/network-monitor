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
    
    # Column mapping: cicflowmeter output -> CICIDS2017 format
    COLUMN_MAPPING = {
        'flow_duration': 'Flow Duration',
        'tot_fwd_pkts': 'Total Fwd Packets',
        'tot_bwd_pkts': 'Total Backward Packets',
        'totlen_fwd_pkts': 'Total Length of Fwd Packets',
        'totlen_bwd_pkts': 'Total Length of Bwd Packets',
        'fwd_pkt_len_max': 'Fwd Packet Length Max',
        'fwd_pkt_len_min': 'Fwd Packet Length Min',
        'fwd_pkt_len_mean': 'Fwd Packet Length Mean',
        'fwd_pkt_len_std': 'Fwd Packet Length Std',
        'bwd_pkt_len_max': 'Bwd Packet Length Max',
        'bwd_pkt_len_min': 'Bwd Packet Length Min',
        'bwd_pkt_len_mean': 'Bwd Packet Length Mean',
        'bwd_pkt_len_std': 'Bwd Packet Length Std',
        'flow_byts_s': 'Flow Bytes/s',
        'flow_pkts_s': 'Flow Packets/s',
        'flow_iat_mean': 'Flow IAT Mean',
        'flow_iat_std': 'Flow IAT Std',
        'flow_iat_max': 'Flow IAT Max',
        'flow_iat_min': 'Flow IAT Min',
        'fwd_iat_tot': 'Fwd IAT Total',
        'fwd_iat_mean': 'Fwd IAT Mean',
        'fwd_iat_std': 'Fwd IAT Std',
        'fwd_iat_max': 'Fwd IAT Max',
        'fwd_iat_min': 'Fwd IAT Min',
        'bwd_iat_tot': 'Bwd IAT Total',
        'bwd_iat_mean': 'Bwd IAT Mean',
        'bwd_iat_std': 'Bwd IAT Std',
        'bwd_iat_max': 'Bwd IAT Max',
        'bwd_iat_min': 'Bwd IAT Min',
        'fwd_psh_flags': 'Fwd PSH Flags',
        'bwd_psh_flags': 'Bwd PSH Flags',
        'fwd_urg_flags': 'Fwd URG Flags',
        'bwd_urg_flags': 'Bwd URG Flags',
        'fwd_header_len': 'Fwd Header Length',
        'bwd_header_len': 'Bwd Header Length',
        'fwd_pkts_s': 'Fwd Packets/s',
        'bwd_pkts_s': 'Bwd Packets/s',
        'pkt_len_min': 'Min Packet Length',
        'pkt_len_max': 'Max Packet Length',
        'pkt_len_mean': 'Packet Length Mean',
        'pkt_len_std': 'Packet Length Std',
        'pkt_len_var': 'Packet Length Variance',
        'fin_flag_cnt': 'FIN Flag Count',
        'syn_flag_cnt': 'SYN Flag Count',
        'rst_flag_cnt': 'RST Flag Count',
        'psh_flag_cnt': 'PSH Flag Count',
        'ack_flag_cnt': 'ACK Flag Count',
        'urg_flag_cnt': 'URG Flag Count',
        'cwr_flag_count': 'CWE Flag Count',
        'ece_flag_cnt': 'ECE Flag Count',
        'down_up_ratio': 'Down/Up Ratio',
        'pkt_size_avg': 'Average Packet Size',
        'fwd_seg_size_avg': 'Avg Fwd Segment Size',
        'bwd_seg_size_avg': 'Avg Bwd Segment Size',
        'fwd_byts_b_avg': 'Fwd Avg Bytes/Bulk',
        'fwd_pkts_b_avg': 'Fwd Avg Packets/Bulk',
        'fwd_blk_rate_avg': 'Fwd Avg Bulk Rate',
        'bwd_byts_b_avg': 'Bwd Avg Bytes/Bulk',
        'bwd_pkts_b_avg': 'Bwd Avg Packets/Bulk',
        'bwd_blk_rate_avg': 'Bwd Avg Bulk Rate',
        'subflow_fwd_pkts': 'Subflow Fwd Packets',
        'subflow_fwd_byts': 'Subflow Fwd Bytes',
        'subflow_bwd_pkts': 'Subflow Bwd Packets',
        'subflow_bwd_byts': 'Subflow Bwd Bytes',
        'init_fwd_win_byts': 'Init_Win_bytes_forward',
        'init_bwd_win_byts': 'Init_Win_bytes_backward',
        'fwd_act_data_pkts': 'act_data_pkt_fwd',
        'fwd_seg_size_min': 'min_seg_size_forward',
        'active_mean': 'Active Mean',
        'active_std': 'Active Std',
        'active_max': 'Active Max',
        'active_min': 'Active Min',
        'idle_mean': 'Idle Mean',
        'idle_std': 'Idle Std',
        'idle_max': 'Idle Max',
        'idle_min': 'Idle Min',
    }
    
    def __init__(self, 
                 input_dir: str = '/input',
                 kafka_servers: List[str] = ['kafka:9092'],
                 kafka_topic: str = 'network-flows',
                 batch_size: int = 1000):
        
        self.input_dir = input_dir
        self.kafka_topic = kafka_topic
        self.batch_size = batch_size
        self.processed_files = set()
        
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
            
            # Check for required columns
            required_cols = ['flow_duration', 'tot_fwd_pkts', 'flow_pkts_s']
            missing_cols = [col for col in required_cols if col not in df_sample.columns]
            
            if missing_cols:
                logger.warning(f"Missing columns {missing_cols} in: {file_path}")
                return False
                
            logger.debug(f"CSV validation passed: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"CSV validation failed for {file_path}: {e}")
            return False
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize data (similar to LSTM preprocessing)
        """
        # Handle inf/nan values
        pd.set_option('mode.use_inf_as_na', True)
        
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
            
        if not self.validate_csv(file_path):
            return 0
            
        try:
            logger.info(f"Processing CSV: {file_path}")
            
            # Read CSV
            df = pd.read_csv(file_path)
            
            # Rename columns to CICIDS2017 format
            df = df.rename(columns=self.COLUMN_MAPPING)
            
            # Clean data
            df = self.clean_data(df)
            
            # Add metadata
            df['source_file'] = os.path.basename(file_path)
            df['processed_at'] = pd.Timestamp.now().isoformat()
            
            # Send to Kafka in batches
            flows_sent = 0
            for start_idx in range(0, len(df), self.batch_size):
                batch = df.iloc[start_idx:start_idx + self.batch_size]
                
                for _, row in batch.iterrows():
                    flow_data = row.to_dict()
                    
                    try:
                        future = self.producer.send(self.kafka_topic, flow_data)
                        future.get(timeout=10)  # Wait for confirmation
                        flows_sent += 1
                        
                    except KafkaError as e:
                        logger.error(f"Failed to send flow to Kafka: {e}")
                        continue
                
                if flows_sent % 100 == 0:
                    logger.info(f"Sent {flows_sent}/{len(df)} flows...")
            
            # Flush producer
            self.producer.flush(timeout=30)
            
            logger.info(f"Successfully processed {flows_sent} flows from {file_path}")
            
            # Mark as processed
            self.processed_files.add(file_path)
            
            # Remove processed file
            os.remove(file_path)
            logger.debug(f"Removed processed file: {file_path}")
            
            return flows_sent
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
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
            'timestamp': pd.Timestamp.now().isoformat()
        }

class CSVWatcher(FileSystemEventHandler):
    """
    File system watcher for CSV files
    """
    
    def __init__(self, processor: FlowProcessor):
        self.processor = processor
        
    def on_created(self, event):
        if event.is_dir:
            return
            
        if event.src_path.endswith('.csv'):
            logger.info(f"New CSV detected: {event.src_path}")
            # Wait a bit to ensure file is fully written
            time.sleep(2)
            self.processor.process_csv(event.src_path)

def main():
    """
    Main function - start the flow processor
    """
    # Configuration from environment
    input_dir = os.getenv('INPUT_DIR', '/input')
    kafka_servers = os.getenv('KAFKA_SERVERS', 'kafka:9092').split(',')
    kafka_topic = os.getenv('KAFKA_TOPIC', 'network-flows')
    batch_size = int(os.getenv('BATCH_SIZE', '1000'))
    
    # Create processor
    processor = FlowProcessor(
        input_dir=input_dir,
        kafka_servers=kafka_servers,
        kafka_topic=kafka_topic,
        batch_size=batch_size
    )
    
    # Process existing files
    if os.path.exists(input_dir):
        for filename in os.listdir(input_dir):
            if filename.endswith('.csv'):
                file_path = os.path.join(input_dir, filename)
                processor.process_csv(file_path)
    
    # Start file watcher
    event_handler = CSVWatcher(processor)
    observer = Observer()
    observer.schedule(event_handler, input_dir, recursive=False)
    observer.start()
    
    logger.info(f"Flow processor started, watching: {input_dir}")
    
    # Graceful shutdown handler
    def signal_handler(signum, frame):
        logger.info("Shutting down flow processor...")
        observer.stop()
        processor.producer.close()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)
    finally:
        observer.join()

if __name__ == "__main__":
    main()