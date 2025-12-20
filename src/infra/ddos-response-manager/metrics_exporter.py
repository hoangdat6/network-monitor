#!/usr/bin/env python3
"""
Prometheus Exporter cho Response Manager
Export metrics từ Redis để Grafana visualize
"""

import os
import time
import redis
import logging
from flask import Flask, Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment config
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
METRICS_PORT = int(os.getenv('METRICS_PORT', '9091'))

# Redis keys
REDIS_KEY_BLOCKED = 'ddos:blocked_ips'
REDIS_KEY_PENDING = 'ddos:pending_ips'
REDIS_KEY_WHITELIST = 'ddos:whitelist_ips'
REDIS_KEY_PREFIX = 'ddos:ip:'

# Prometheus metrics
ddos_pending_ips_count = Gauge('ddos_pending_ips_count', 'Number of IPs pending approval')
ddos_blocked_ips_count = Gauge('ddos_blocked_ips_count', 'Number of IPs currently blocked')
ddos_whitelisted_ips_count = Gauge('ddos_whitelisted_ips_count', 'Number of whitelisted IPs')
ddos_attacks_detected_total = Counter('ddos_attacks_detected_total', 'Total DDoS attacks detected')

ddos_ip_metadata = Gauge(
    'ddos_ip_metadata',
    'IP metadata from DDoS detection',
    ['ip', 'severity', 'attack_type', 'block_status', 'confidence', 'flow_count', 'alert_count', 'first_seen', 'last_seen', 'block_duration', 'ttl_seconds']
)

class ResponseManagerExporter:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        
        self.app = Flask(__name__)
        self._setup_routes()
        
    def _setup_routes(self):
        @self.app.route('/metrics', methods=['GET'])
        def metrics():
            """Prometheus metrics endpoint"""
            try:
                self._update_metrics()
                return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
            except Exception as e:
                logger.error(f"Error generating metrics: {e}")
                return Response(f"Error: {str(e)}", status=500)
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check"""
            return {'status': 'healthy', 'redis_connected': self._check_redis()}, 200
    
    def _check_redis(self) -> bool:
        """Check Redis connection"""
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def _update_metrics(self):
        """Update all Prometheus metrics from Redis"""
        try:
            # Count metrics
            pending_count = self.redis_client.scard(REDIS_KEY_PENDING)
            blocked_count = self.redis_client.scard(REDIS_KEY_BLOCKED)
            whitelist_count = self.redis_client.scard(REDIS_KEY_WHITELIST)
            
            ddos_pending_ips_count.set(pending_count)
            ddos_blocked_ips_count.set(blocked_count)
            ddos_whitelisted_ips_count.set(whitelist_count)
            
            # Clear previous IP metadata metrics
            ddos_ip_metadata._metrics.clear()
            
            # Export metadata for all IPs
            all_ip_sets = [
                (REDIS_KEY_PENDING, 'pending'),
                (REDIS_KEY_BLOCKED, 'blocked'),
                (REDIS_KEY_WHITELIST, 'whitelisted')
            ]
            
            for redis_key, status in all_ip_sets:
                ips = self.redis_client.smembers(redis_key)
                
                for ip in ips:
                    metadata_key = f"{REDIS_KEY_PREFIX}{ip}"
                    metadata = self.redis_client.hgetall(metadata_key)
                    
                    if not metadata:
                        continue
                    
                    # Get TTL for blocked IPs
                    ttl = 0
                    if status == 'blocked':
                        ttl = self.redis_client.ttl(metadata_key)
                        if ttl < 0:
                            ttl = 0
                    
                    # Create metric labels
                    labels = {
                        'ip': ip,
                        'severity': metadata.get('severity', 'unknown'),
                        'attack_type': metadata.get('attack_type', 'unknown'),
                        'block_status': status,
                        'confidence': str(metadata.get('confidence', '0.0')),
                        'flow_count': str(metadata.get('flow_count', '0')),
                        'alert_count': str(metadata.get('alert_count', '0')),
                        'first_seen': metadata.get('first_seen', ''),
                        'last_seen': metadata.get('last_seen', ''),
                        'block_duration': str(metadata.get('block_duration', '0')),
                        'ttl_seconds': str(ttl)
                    }
                    
                    # Set metric value = 1 (indicates IP exists)
                    ddos_ip_metadata.labels(**labels).set(1)
            
            logger.debug(f"Metrics updated: pending={pending_count}, blocked={blocked_count}, whitelist={whitelist_count}")
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    def run(self):
        """Run exporter"""
        logger.info(f"Starting Prometheus exporter on port {METRICS_PORT}")
        self.app.run(host='0.0.0.0', port=METRICS_PORT, debug=False)

def main():
    logger.info("🚀 Starting Response Manager Prometheus Exporter...")
    exporter = ResponseManagerExporter()
    exporter.run()

if __name__ == "__main__":
    main()
