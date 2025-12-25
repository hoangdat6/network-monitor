"""
Rule-Based DDoS Detector

Consumes flows from Kafka, applies rules, and produces:
- Alerts to ddos-alerts topic (if rule matches)
- Clean flows to flows-for-ml topic (if no match)
"""

import os
import sys
import json
import time
import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, asdict

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import prometheus_client as prom
from prometheus_client import Counter, Gauge, Histogram, start_http_server

from rule_engine import RuleEngine, RuleMatch
from window_manager import WindowManager
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
FLOWS_PROCESSED = Counter('rule_detector_flows_processed_total', 'Total flows processed')
FLOWS_MATCHED = Counter('rule_detector_flows_matched_total', 'Flows matched by rules', ['rule_id'])
FLOWS_TO_ML = Counter('rule_detector_flows_to_ml_total', 'Flows sent to ML')
ALERTS_TRIGGERED = Counter('rule_detector_alerts_total', 'Alerts triggered', ['severity', 'rule_id', 'rule_name'])
WINDOW_FLOWS = Gauge('rule_detector_window_flows', 'Flows in window', ['window'])
PROCESSING_TIME = Histogram('rule_detector_processing_seconds', 'Time to process flow')


@dataclass
class Alert:
    """DDoS Alert from rule-based detection"""
    alert_id: str
    source: str  # "rule-based"
    rule_id: str
    rule_name: str
    severity: str
    description: str
    timestamp: datetime
    attacker_ips: list
    matched_conditions: list
    action: str
    confidence: float = 1.0
    window_stats: dict = None


class RuleBasedDetector:
    """
    Main detector service
    Reads from network-flows, applies rules, outputs to ddos-alerts or flows-for-ml
    """
    
    def __init__(self, rules_path: str, kafka_servers: list):
        # Load configuration
        with open(rules_path, 'r') as f:
            rules_config = yaml.safe_load(f)
        
        self.config = rules_config.get('config', {})
        
        # Initialize components
        self.rule_engine = RuleEngine(rules_path)
        self.window_manager = WindowManager(self.config['windows'])
        
        # Kafka topics
        kafka_config = self.config['kafka']
        self.input_topic = kafka_config['input_topic']
        self.alert_topic = kafka_config['output_alert_topic']
        self.ml_topic = kafka_config['output_ml_topic']
        
        # Kafka consumer
        self.consumer = KafkaConsumer(
            self.input_topic,
            bootstrap_servers=kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='rule-based-detector-group'
        )
        
        # Kafka producers
        self.alert_producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        
        self.ml_producer = KafkaProducer(
            bootstrap_servers=kafka_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        
        # Alert tracking (cooldown)
        self.last_alert_time = {}
        self.alert_cooldown = self.config['alert']['cooldown']
        
        # Performance settings
        self.flows_processed = 0
        self.analysis_interval = self.config['performance'].get('batch_size', 100)
        
        logger.info("Rule-Based Detector initialized")
        logger.info(f"Input topic: {self.input_topic}")
        logger.info(f"Alert topic: {self.alert_topic}")
        logger.info(f"ML topic: {self.ml_topic}")
    
    def process_flow(self, flow_data: Dict) -> bool:
        """
        Process a single flow
        
        Returns:
            True if flow matched a rule (alert sent)
            False if no match (flow sent to ML)
        """
        with PROCESSING_TIME.time():
            # Check per-flow rules first (fast path)
            rule_match = self.rule_engine.check_per_flow(flow_data)
            
            if rule_match:
                # Rule matched - send alert
                self._send_alert(rule_match, flow_data)
                FLOWS_MATCHED.labels(rule_id=rule_match.rule_id).inc()
                return True
            
            # No per-flow match - add to window for aggregation
            self.window_manager.add_flow(flow_data)
            
            # Send to ML for further analysis
            self._send_to_ml(flow_data)
            FLOWS_TO_ML.inc()
            
            return False
    
    def analyze_windows(self):
        """
        Periodically check aggregation rules
        Called every N flows
        """
        for window_name in self.window_manager.windows.keys():
            stats = self.window_manager.get_statistics(window_name)
            
            if not stats:
                continue
            
            # Update metrics
            WINDOW_FLOWS.labels(window=window_name).set(stats.get('total_flows', 0))
            
            # Check aggregation rules (returns list of matches)
            rule_matches = self.rule_engine.check_aggregation(stats)
            
            if rule_matches:
                # Get top attackers
                top_attackers = self.window_manager.get_top_attackers(window_name)
                attacker_ips = [a['ip'] for a in top_attackers]
                
                # Send alert for EACH matched rule
                for rule_match in rule_matches:
                    self._send_alert(rule_match, None, attacker_ips, stats)
                    FLOWS_MATCHED.labels(rule_id=rule_match.rule_id).inc()
    
    def _send_alert(self, rule_match: RuleMatch, flow_data: Optional[Dict] = None,
                    attacker_ips: list = None, window_stats: dict = None):
        """Send alert to Kafka"""
        # Check cooldown
        alert_key = f"{rule_match.rule_id}"
        current_time = time.time()
        
        if alert_key in self.last_alert_time:
            if (current_time - self.last_alert_time[alert_key]) < self.alert_cooldown:
                logger.debug(f"Alert cooldown active for {alert_key}")
                return
        
        # Determine attacker IPs
        if attacker_ips is None and flow_data:
            attacker_ips = [flow_data.get('src_ip', 'unknown')]
        elif attacker_ips is None:
            attacker_ips = []
        
        # Create alert
        alert = Alert(
            alert_id=f"rule_{rule_match.rule_id}_{int(current_time)}",
            source="rule-based",
            rule_id=rule_match.rule_id,
            rule_name=rule_match.name,
            severity=rule_match.severity,
            description=rule_match.description,
            timestamp=datetime.now(),
            attacker_ips=attacker_ips,
            matched_conditions=rule_match.matched_conditions,
            action=rule_match.action,
            confidence=rule_match.confidence,
            window_stats=window_stats
        )
        
        # Send to Kafka
        try:
            self.alert_producer.send(self.alert_topic, asdict(alert))
            self.alert_producer.flush()
            
            ALERTS_TRIGGERED.labels(
                severity=rule_match.severity,
                rule_id=rule_match.rule_id,
                rule_name=rule_match.name
            ).inc()
            
            logger.warning(
                f"🚨 ALERT [{rule_match.severity.upper()}] - {rule_match.name} "
                f"(Rule: {rule_match.rule_id}) - IPs: {', '.join(attacker_ips[:3])}"
            )
            
            # Update cooldown
            self.last_alert_time[alert_key] = current_time
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def _send_to_ml(self, flow_data: Dict):
        """Send flow to ML topic for further analysis"""
        try:
            self.ml_producer.send(self.ml_topic, flow_data)
        except Exception as e:
            logger.error(f"Failed to send flow to ML: {e}")
    
    def run(self):
        """Main detection loop"""
        logger.info(f"Starting rule-based detection on topic: {self.input_topic}")
        
        try:
            for message in self.consumer:
                flow_data = message.value
                
                # Process flow
                self.process_flow(flow_data)
                
                FLOWS_PROCESSED.inc()
                self.flows_processed += 1
                
                # Periodically analyze windows
                if self.flows_processed % self.analysis_interval == 0:
                    self.analyze_windows()
                    
                    # Flush ML producer
                    self.ml_producer.flush()
                
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.consumer.close()
            self.alert_producer.close()
            self.ml_producer.close()


def main():
    """Main entry point"""
    # Configuration
    RULES_PATH = os.getenv('RULES_PATH', '/app/rules.yaml')
    if not os.path.exists(RULES_PATH):
        RULES_PATH = Path(__file__).parent / 'rules.yaml'
    
    KAFKA_SERVERS = os.getenv('KAFKA_BROKERS', 'kafka:9092').split(',')
    METRICS_PORT = int(os.getenv('METRICS_PORT', '8000'))
    
    # Check required files
    if not os.path.exists(RULES_PATH):
        logger.error(f"Rules file not found: {RULES_PATH}")
        sys.exit(1)
    
    # Start Prometheus metrics server
    start_http_server(METRICS_PORT)
    logger.info(f"Prometheus metrics server started on port {METRICS_PORT}")
    
    # Create and run detector
    detector = RuleBasedDetector(
        rules_path=str(RULES_PATH),
        kafka_servers=KAFKA_SERVERS
    )
    
    # Graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    detector.run()


if __name__ == "__main__":
    main()
