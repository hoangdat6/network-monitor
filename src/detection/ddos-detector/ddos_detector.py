"""
DDoS Detector với Sliding Window Aggregation

Chiến lược phát hiện DDoS:
1. **Per-flow classification**: Dự đoán xác suất DDoS cho từng flow
2. **Time-based aggregation**: Tổng hợp flows trong sliding window (30s, 60s)
3. **Multi-level scoring**: 
   - Flow-level: ML model prediction
   - IP-level: Số lượng suspicious flows từ cùng 1 IP
   - Network-level: Tổng số suspicious flows trong time window
4. **Threshold-based alerting**: Chỉ alert khi vượt ngưỡng tổng hợp

Tại sao cần aggregation:
- Single flow prediction có thể là false positive
- DDoS = nhiều flows bất thường cùng lúc
- Cần xem xét context: volume, pattern, timing

Output:
- Kafka topic: ddos-alerts (chỉ real threats)
- Prometheus metrics: ddos_flow_count, ddos_alert_count
- Log: Chi tiết từng detection event
"""

import os
import sys
import json
import time
import logging
import joblib
import numpy as np
import pandas as pd
import yaml
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import prometheus_client as prom
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
FLOW_PROCESSED = Counter('ddos_flows_processed_total', 'Total flows processed')
FLOW_SUSPICIOUS = Counter('ddos_flows_suspicious_total', 'Suspicious flows detected', ['attack_type'])
ALERT_TRIGGERED = Counter('ddos_alerts_triggered_total', 'DDoS alerts triggered', ['severity'])
PREDICTION_TIME = Histogram('ddos_prediction_seconds', 'Time to predict flow')
ACTIVE_ATTACKERS = Gauge('ddos_active_attackers', 'Number of active attacking IPs')
FLOWS_IN_WINDOW = Gauge('ddos_flows_in_window', 'Flows in current time window')

@dataclass
class FlowPrediction:
    """Single flow prediction result"""
    timestamp: datetime
    src_ip: str
    dst_ip: str
    src_port: float
    dst_port: float
    protocol: float
    prediction: str
    confidence: float
    features: Dict[str, float]

@dataclass
class DDoSAlert:
    """DDoS attack alert"""
    alert_id: str
    timestamp: datetime
    severity: str  # low, medium, high, critical
    attack_type: str
    attacker_ips: List[str]
    target_ip: str
    flow_count: int
    avg_confidence: float
    time_window: str
    metrics: Dict[str, float]
    recommendation: str

class SlidingWindow:
    """
    Sliding window để track flows theo thời gian
    """
    def __init__(self, window_size: int = 60):
        self.window_size = window_size  # seconds
        self.flows = deque()
        self.ip_flows = defaultdict(list)  # IP -> [flows]
        
    def add_flow(self, prediction: FlowPrediction):
        """Add flow to window"""
        self.flows.append(prediction)
        if prediction.prediction != 'BENIGN':
            self.ip_flows[prediction.src_ip].append(prediction)
        
        # Remove old flows
        self._cleanup()
    
    def _cleanup(self):
        """Remove flows outside time window"""
        cutoff_time = datetime.now() - timedelta(seconds=self.window_size)
        
        # Clean main flows
        while self.flows and self.flows[0].timestamp < cutoff_time:
            old_flow = self.flows.popleft()
            
        # Clean IP flows
        for ip in list(self.ip_flows.keys()):
            self.ip_flows[ip] = [
                f for f in self.ip_flows[ip] 
                if f.timestamp >= cutoff_time
            ]
            if not self.ip_flows[ip]:
                del self.ip_flows[ip]
    
    def get_stats(self) -> Dict:
        """Get window statistics"""
        self._cleanup()
        
        total_flows = len(self.flows)
        suspicious_flows = sum(1 for f in self.flows if f.prediction != 'BENIGN')
        unique_attackers = len(self.ip_flows)
        
        # IP với nhiều suspicious flows nhất
        top_attackers = sorted(
            self.ip_flows.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:10]
        
        return {
            'total_flows': total_flows,
            'suspicious_flows': suspicious_flows,
            'suspicious_ratio': suspicious_flows / max(total_flows, 1),
            'unique_attackers': unique_attackers,
            'top_attackers': [
                {'ip': ip, 'flow_count': len(flows)}
                for ip, flows in top_attackers
            ]
        }

class DDoSDetector:
    """
    Main DDoS detector với ML model và aggregation logic
    """
    
    def __init__(self, 
                 model_path: str,
                 features_path: str,
                 threshold_path: str,
                 rules_path: str,
                 kafka_input_topic: str = 'network-flows',
                 kafka_output_topic: str = 'ddos-alerts',
                 kafka_servers: List[str] = ['kafka:9092']):
        
        self.kafka_input_topic = kafka_input_topic
        self.kafka_output_topic = kafka_output_topic
        self.kafka_servers = kafka_servers
        
        # Load detection rules from YAML
        logger.info(f"Loading detection rules from: {rules_path}")
        with open(rules_path, 'r') as f:
            self.rules = yaml.safe_load(f)
        
        self.thresholds = self.rules['thresholds']
        self.recommendations = self.rules['recommendations']
        self.alert_config = self.rules['alert']
        self.ip_whitelist = set(self.rules['ip_filtering']['whitelist'])
        self.ip_blacklist = set(self.rules['ip_filtering']['blacklist'])
        self.analysis_interval = self.rules['performance']['analysis_interval']
        
        logger.info(f"Rules loaded: {len(self.thresholds)} severity levels")
        
        # Load ML model (XGBoost Calibrated)
        logger.info("Loading ML model...")
        self.model = joblib.load(model_path)
        logger.info(f"Model loaded: {type(self.model).__name__}")
        
        # Load feature list (30 features for reduced model)
        self.required_features = joblib.load(features_path)
        logger.info(f"Features loaded: {len(self.required_features)} features")
        
        # Load threshold configuration
        with open(threshold_path, 'r') as f:
            threshold_config = json.load(f)
        self.classification_threshold = threshold_config.get('threshold', 0.98)
        logger.info(f"Classification threshold: {self.classification_threshold}")
        
        # Initialize sliding windows from config
        self.windows = {}
        self.primary_window = None
        for name, config in self.rules['time_windows'].items():
            if config['enabled']:
                window_key = f"{config['size']}s"
                self.windows[window_key] = SlidingWindow(config['size'])
                if config.get('primary', False):
                    self.primary_window = window_key
                logger.info(f"Window '{name}': {config['size']}s - {config['description']}")
        
        if not self.primary_window:
            # Fallback to first window if no primary specified
            self.primary_window = list(self.windows.keys())[0]
        
        # Alert tracking
        self.last_alert_time = defaultdict(lambda: datetime.min)
        self.alert_history = deque(maxlen=self.rules['performance']['max_alert_history'])
        
        # Kafka consumer
        self.consumer = KafkaConsumer(
            kafka_input_topic,
            bootstrap_servers=kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='ddos-detector-group'
        )
        
        # Kafka producer for alerts
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        
        logger.info("DDoS Detector initialized")
    
    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        return ip in self.ip_whitelist
    
    def is_blacklisted(self, ip: str) -> bool:
        """Check if IP is blacklisted"""
        return ip in self.ip_blacklist
    
    def extract_features(self, flow_data: Dict) -> Optional[np.ndarray]:
        """
        Extract features từ flow data (30 features cho reduced model)
        """
        try:
            features = []
            for feature_name in self.required_features:
                value = flow_data.get(feature_name, 0.0)
                
                # Handle NaN/inf
                if pd.isna(value) or np.isinf(value):
                    value = 0.0
                
                features.append(float(value))
            
            if len(features) != len(self.required_features):
                logger.error(f"Feature count mismatch: expected {len(self.required_features)}, got {len(features)}")
                return None
            
            return np.array(features).reshape(1, -1)
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None
    
    def predict_flow(self, flow_data: Dict) -> Optional[FlowPrediction]:
        """
        Predict single flow
        """
        try:
            src_ip = flow_data.get('src_ip', 'unknown')
            
            # Check whitelist/blacklist
            if self.is_whitelisted(src_ip):
                return None  # Skip whitelisted IPs
            
            with PREDICTION_TIME.time():
                # Extract features
                features = self.extract_features(flow_data)
                if features is None:
                    return None
                
                # Predict with calibrated model
                prediction_proba = self.model.predict_proba(features)[0]
                
                # Get probability for attack class (assuming binary: 0=BENIGN, 1=ATTACK)
                attack_proba = float(prediction_proba[1])
                
                # Apply threshold
                prediction = 1 if attack_proba >= self.classification_threshold else 0
                
                # Get label
                label = 'DDoS' if prediction == 1 else 'BENIGN'
                confidence = attack_proba if prediction == 1 else (1 - attack_proba)
                
                # Override if blacklisted
                if self.is_blacklisted(src_ip):
                    label = 'DDoS'
                    confidence = 1.0
                    attack_proba = 1.0
                
                # Create prediction object
                result = FlowPrediction(
                    timestamp=datetime.now(),
                    src_ip=src_ip,
                    dst_ip=flow_data.get('dst_ip', 'unknown'),
                    src_port=flow_data.get('src_port', 0),
                    dst_port=flow_data.get('dst_port', 0),
                    protocol=flow_data.get('protocol', 0),
                    prediction=label,
                    confidence=confidence,
                    features={
                        name: float(flow_data.get(name, 0))
                        for name in self.required_features[:5]  # Top 5 features for logging
                    }
                )
                
                FLOW_PROCESSED.inc()
                if label != 'BENIGN':
                    FLOW_SUSPICIOUS.labels(attack_type=label).inc()
                
                return result
                
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None
    
    def analyze_windows(self) -> Optional[DDoSAlert]:
        """
        Analyze all time windows và quyết định có trigger alert không
        """
        # Analyze primary window
        stats = self.windows[self.primary_window].get_stats()
        
        FLOWS_IN_WINDOW.set(stats['total_flows'])
        ACTIVE_ATTACKERS.set(stats['unique_attackers'])
        
        # Không đủ data để phân tích
        min_flows = self.alert_config['min_flows_for_analysis']
        if stats['total_flows'] < min_flows:
            return None
        
        # Determine severity based on thresholds
        severity = self._calculate_severity(stats)
        
        if severity is None:
            return None
        
        # Check alert cooldown
        alert_type = f"ddos_{severity}"
        cooldown = self.alert_config['cooldown']
        if (datetime.now() - self.last_alert_time[alert_type]).total_seconds() < cooldown:
            logger.debug(f"Alert cooldown active for {alert_type}")
            return None
        
        # Create alert
        alert = self._create_alert(severity, stats)
        
        # Update tracking
        self.last_alert_time[alert_type] = datetime.now()
        self.alert_history.append(alert)
        
        ALERT_TRIGGERED.labels(severity=severity).inc()
        
        return alert
    
    def _calculate_severity(self, stats: Dict) -> Optional[str]:
        """
        Calculate alert severity based on statistics
        """
        suspicious_count = stats['suspicious_flows']
        suspicious_ratio = stats['suspicious_ratio']
        
        # Check từ critical -> low (theo thứ tự trong config)
        severity_levels = ['critical', 'high', 'medium', 'low']
        for severity in severity_levels:
            if severity not in self.thresholds:
                continue
                
            threshold = self.thresholds[severity]
            
            if (suspicious_count >= threshold['min_flows'] and
                suspicious_ratio >= threshold['min_suspicious_ratio']):
                return severity
        
        return None
    
    def _create_alert(self, severity: str, stats: Dict) -> DDoSAlert:
        """
        Create DDoS alert object
        """
        top_count = self.alert_config['top_attackers_count']
        top_attackers = [item['ip'] for item in stats['top_attackers'][:top_count]]
        
        alert = DDoSAlert(
            alert_id=f"ddos_{int(time.time())}",
            timestamp=datetime.now(),
            severity=severity,
            attack_type='DDoS_Mixed',
            attacker_ips=top_attackers,
            target_ip='server',  # TODO: detect actual target
            flow_count=stats['suspicious_flows'],
            avg_confidence=0.0,  # Calculate if needed
            time_window=self.primary_window,
            metrics={
                'total_flows': stats['total_flows'],
                'suspicious_ratio': stats['suspicious_ratio'],
                'unique_attackers': stats['unique_attackers']
            },
            recommendation=self.recommendations.get(severity, 'Unknown severity level')
        )
        
        return alert
    
    def send_alert(self, alert: DDoSAlert):
        """
        Send alert to Kafka
        """
        try:
            alert_data = asdict(alert)
            self.producer.send(self.kafka_output_topic, alert_data)
            self.producer.flush()
            
            logger.warning(
                f"🚨 DDoS ALERT [{alert.severity.upper()}] - "
                f"{alert.flow_count} suspicious flows from {len(alert.attacker_ips)} IPs"
            )
            logger.warning(f"   Top attackers: {', '.join(alert.attacker_ips[:3])}")
            logger.warning(f"   Recommendation: {alert.recommendation}")
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def run(self):
        """
        Main detection loop
        """
        logger.info(f"Starting DDoS detection on topic: {self.kafka_input_topic}")
        
        try:
            for message in self.consumer:
                flow_data = message.value
                
                # Predict flow
                prediction = self.predict_flow(flow_data)
                if prediction is None:
                    continue
                
                # Add to windows
                for window in self.windows.values():
                    window.add_flow(prediction)
                
                # Log suspicious flows
                if prediction.prediction != 'BENIGN':
                    logger.info(
                        f"Suspicious flow: {prediction.src_ip} -> {prediction.dst_ip} | "
                        f"Type: {prediction.prediction} | Confidence: {prediction.confidence:.2f}"
                    )
                
                # Analyze windows every N flows (từ config)
                if FLOW_PROCESSED._value._value % self.analysis_interval == 0:
                    alert = self.analyze_windows()
                    if alert:
                        self.send_alert(alert)
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.consumer.close()
            self.producer.close()

def main():
    """
    Main entry point
    """
    # Configuration
    MODEL_DIR = os.getenv('MODEL_DIR', '/models')
    MODEL_PATH = os.path.join(MODEL_DIR, 'xgb_calibrated_model_reduced.joblib')
    FEATURES_PATH = os.path.join(MODEL_DIR, 'features_reduced.pkl')
    THRESHOLD_PATH = os.path.join(MODEL_DIR, 'threshold_reduced.json')
    
    # Rules configuration
    RULES_PATH = os.getenv('RULES_PATH', '/app/detection_rules.yaml')
    if not os.path.exists(RULES_PATH):
        # Fallback to local path
        RULES_PATH = Path(__file__).parent / 'detection_rules.yaml'
    
    KAFKA_SERVERS = os.getenv('KAFKA_BROKERS', 'kafka:9092').split(',')
    KAFKA_INPUT_TOPIC = os.getenv('KAFKA_INPUT_TOPIC', 'network-flows')
    KAFKA_OUTPUT_TOPIC = os.getenv('KAFKA_OUTPUT_TOPIC', 'ddos-alerts')
    
    METRICS_PORT = int(os.getenv('METRICS_PORT', '8000'))
    
    # Check required files
    required_files = [MODEL_PATH, FEATURES_PATH, THRESHOLD_PATH, RULES_PATH]
    for path in required_files:
        if not os.path.exists(path):
            logger.error(f"Required file not found: {path}")
            sys.exit(1)
    
    # Start Prometheus metrics server
    start_http_server(METRICS_PORT)
    logger.info(f"Prometheus metrics server started on port {METRICS_PORT}")
    
    # Create and run detector
    detector = DDoSDetector(
        model_path=MODEL_PATH,
        features_path=FEATURES_PATH,
        threshold_path=THRESHOLD_PATH,
        rules_path=str(RULES_PATH),
        kafka_input_topic=KAFKA_INPUT_TOPIC,
        kafka_output_topic=KAFKA_OUTPUT_TOPIC,
        kafka_servers=KAFKA_SERVERS
    )
    
    detector.run()

if __name__ == "__main__":
    main()
