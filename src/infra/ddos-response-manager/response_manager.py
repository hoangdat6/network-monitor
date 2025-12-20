"""
DDoS Response Manager

Chức năng:
1. Lắng nghe alerts từ Kafka topic 'ddos-alerts'
2. Lưu IP metadata vào Redis với các thông tin:
   - IP address
   - Severity level
   - Flow count
   - Confidence score
   - First seen / Last seen
   - Block status (pending/approved/blocked)
   - TTL (auto-expire)
3. Expose REST API cho Grafana/Admin:
   - GET /ips - Danh sách IPs đang pending review
   - POST /ips/{ip}/approve - Admin approve block IP
   - POST /ips/{ip}/reject - Admin reject (whitelist)
   - GET /ips/blocked - Danh sách IPs đang bị block
4. Tích hợp Nginx:
   - Gọi Nginx API để add IP vào blocklist
   - Auto-unblock sau TTL
   - Rate limiting dynamic

Kiến trúc:
Kafka → Response Manager → Redis (metadata)
                ↓
        Nginx API (block IPs)
                ↓
        Grafana Dashboard (review)
"""

import os
import json
import time
import logging
import redis
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from flask import Flask, jsonify, request
from kafka import KafkaConsumer
import threading

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
KAFKA_SERVERS = os.getenv('KAFKA_BROKERS', 'kafka:9092').split(',')
KAFKA_ALERT_TOPIC = os.getenv('KAFKA_ALERT_TOPIC', 'ddos-alerts')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
NGINX_API_URL = os.getenv('NGINX_API_URL', 'http://nginx:8080/api')
API_PORT = int(os.getenv('API_PORT', '5000'))

# Default block duration (seconds)
DEFAULT_BLOCK_DURATION = int(os.getenv('DEFAULT_BLOCK_DURATION', '3600'))  # 1 hour

# Redis keys
REDIS_KEY_PREFIX = 'ddos:ip:'
REDIS_KEY_BLOCKED = 'ddos:blocked_ips'
REDIS_KEY_PENDING = 'ddos:pending_ips'
REDIS_KEY_WHITELIST = 'ddos:whitelist_ips'

@dataclass
class IPMetadata:
    """Metadata cho mỗi IP bị detect"""
    ip: str
    severity: str
    attack_type: str
    flow_count: int
    confidence: float
    first_seen: str
    last_seen: str
    block_status: str  # pending, approved, blocked, whitelisted, rejected
    block_duration: int  # seconds
    alert_count: int  # Số lần bị alert
    
class ResponseManager:
    """
    Main Response Manager class
    """
    def __init__(self):
        # Redis connection
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True
        )
        logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        
        # Kafka consumer
        self.consumer = KafkaConsumer(
            KAFKA_ALERT_TOPIC,
            bootstrap_servers=KAFKA_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='ddos-response-manager'
        )
        logger.info(f"Connected to Kafka topic: {KAFKA_ALERT_TOPIC}")
        
        # Flask app for API
        self.app = Flask(__name__)
        self._setup_routes()
        
    def _setup_routes(self):
        """Setup Flask API routes"""
        
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
        
        @self.app.route('/ips/pending', methods=['GET'])
        def get_pending_ips():
            """Get danh sách IPs đang chờ review"""
            try:
                pending_ips = self.redis_client.smembers(REDIS_KEY_PENDING)
                ip_list = []
                
                for ip in pending_ips:
                    metadata = self._get_ip_metadata(ip)
                    if metadata:
                        ip_list.append(asdict(metadata))
                
                return jsonify({
                    'count': len(ip_list),
                    'ips': sorted(ip_list, key=lambda x: x['alert_count'], reverse=True)
                })
            except Exception as e:
                logger.error(f"Error getting pending IPs: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/ips/blocked', methods=['GET'])
        def get_blocked_ips():
            """Get danh sách IPs đang bị block"""
            try:
                blocked_ips = self.redis_client.smembers(REDIS_KEY_BLOCKED)
                ip_list = []
                
                for ip in blocked_ips:
                    metadata = self._get_ip_metadata(ip)
                    if metadata:
                        # Check TTL
                        ttl = self.redis_client.ttl(f"{REDIS_KEY_PREFIX}{ip}")
                        data = asdict(metadata)
                        data['ttl_seconds'] = ttl
                        ip_list.append(data)
                
                return jsonify({
                    'count': len(ip_list),
                    'ips': sorted(ip_list, key=lambda x: x['last_seen'], reverse=True)
                })
            except Exception as e:
                logger.error(f"Error getting blocked IPs: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/ips/<ip>/approve', methods=['POST'])
        def approve_block(ip):
            """Admin approve block IP"""
            try:
                # Get duration from request or use default
                data = request.get_json() or {}
                duration = data.get('duration', DEFAULT_BLOCK_DURATION)
                
                # Update metadata
                metadata = self._get_ip_metadata(ip)
                if not metadata:
                    return jsonify({'error': 'IP not found'}), 404
                
                metadata.block_status = 'approved'
                metadata.block_duration = duration
                self._save_ip_metadata(metadata)
                
                # Move from pending to blocked
                self.redis_client.srem(REDIS_KEY_PENDING, ip)
                self.redis_client.sadd(REDIS_KEY_BLOCKED, ip)
                
                # Block IP via Nginx
                success = self._block_ip_nginx(ip, duration)
                
                if success:
                    metadata.block_status = 'blocked'
                    self._save_ip_metadata(metadata)
                    
                    logger.info(f"✅ IP {ip} approved and blocked for {duration}s")
                    return jsonify({
                        'status': 'success',
                        'message': f'IP {ip} blocked for {duration} seconds',
                        'metadata': asdict(metadata)
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': 'Failed to block IP via Nginx'
                    }), 500
                    
            except Exception as e:
                logger.error(f"Error approving IP {ip}: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/ips/<ip>/reject', methods=['POST'])
        def reject_block(ip):
            """Admin reject (add to whitelist)"""
            try:
                metadata = self._get_ip_metadata(ip)
                if not metadata:
                    return jsonify({'error': 'IP not found'}), 404
                
                metadata.block_status = 'whitelisted'
                self._save_ip_metadata(metadata)
                
                # Move to whitelist
                self.redis_client.srem(REDIS_KEY_PENDING, ip)
                self.redis_client.sadd(REDIS_KEY_WHITELIST, ip)
                
                logger.info(f"✅ IP {ip} added to whitelist")
                return jsonify({
                    'status': 'success',
                    'message': f'IP {ip} whitelisted',
                    'metadata': asdict(metadata)
                })
                
            except Exception as e:
                logger.error(f"Error rejecting IP {ip}: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/ips/<ip>/unblock', methods=['POST'])
        def unblock_ip(ip):
            """Manually unblock IP"""
            try:
                # Remove from blocked set
                self.redis_client.srem(REDIS_KEY_BLOCKED, ip)
                
                # Update metadata
                metadata = self._get_ip_metadata(ip)
                if metadata:
                    metadata.block_status = 'unblocked'
                    self._save_ip_metadata(metadata)
                
                # Unblock via Nginx
                self._unblock_ip_nginx(ip)
                
                logger.info(f"✅ IP {ip} manually unblocked")
                return jsonify({
                    'status': 'success',
                    'message': f'IP {ip} unblocked'
                })
                
            except Exception as e:
                logger.error(f"Error unblocking IP {ip}: {e}")
                return jsonify({'error': str(e)}), 500
    
    def _get_ip_metadata(self, ip: str) -> Optional[IPMetadata]:
        """Get IP metadata from Redis"""
        try:
            key = f"{REDIS_KEY_PREFIX}{ip}"
            data = self.redis_client.hgetall(key)
            
            if not data:
                return None
            
            return IPMetadata(
                ip=ip,
                severity=data.get('severity', 'unknown'),
                attack_type=data.get('attack_type', 'unknown'),
                flow_count=int(data.get('flow_count', 0)),
                confidence=float(data.get('confidence', 0.0)),
                first_seen=data.get('first_seen', ''),
                last_seen=data.get('last_seen', ''),
                block_status=data.get('block_status', 'unknown'),
                block_duration=int(data.get('block_duration', 0)),
                alert_count=int(data.get('alert_count', 0))
            )
        except Exception as e:
            logger.error(f"Error getting metadata for {ip}: {e}")
            return None
    
    def _save_ip_metadata(self, metadata: IPMetadata):
        """Save IP metadata to Redis"""
        try:
            key = f"{REDIS_KEY_PREFIX}{metadata.ip}"
            data = asdict(metadata)
            
            # Save to Redis hash
            self.redis_client.hset(key, mapping=data)
            
            # Set TTL if blocked
            if metadata.block_status == 'blocked' and metadata.block_duration > 0:
                self.redis_client.expire(key, metadata.block_duration)
            
        except Exception as e:
            logger.error(f"Error saving metadata for {metadata.ip}: {e}")
    
    def _block_ip_nginx(self, ip: str, duration: int) -> bool:
        """
        Block IP via Nginx API
        
        Tùy vào setup Nginx của bạn:
        - Option 1: Nginx Plus API
        - Option 2: Reload config file
        - Option 3: Lua API
        """
        try:
            # TODO: Implement actual Nginx blocking
            # Ví dụ với Nginx Plus API:
            # response = requests.post(
            #     f"{NGINX_API_URL}/keyvals/blocked_ips",
            #     json={ip: "1"}
            # )
            
            # Hoặc write to file và reload:
            # with open('/etc/nginx/blocked_ips.conf', 'a') as f:
            #     f.write(f"deny {ip};\n")
            # os.system('nginx -s reload')
            
            logger.info(f"🚫 Blocking IP {ip} for {duration}s (Nginx integration pending)")
            return True
            
        except Exception as e:
            logger.error(f"Error blocking IP {ip} via Nginx: {e}")
            return False
    
    def _unblock_ip_nginx(self, ip: str) -> bool:
        """Unblock IP via Nginx"""
        try:
            # TODO: Implement actual Nginx unblocking
            logger.info(f"✅ Unblocking IP {ip} (Nginx integration pending)")
            return True
        except Exception as e:
            logger.error(f"Error unblocking IP {ip}: {e}")
            return False
    
    def process_alert(self, alert_data: Dict):
        """
        Process incoming DDoS alert from Kafka
        """
        try:
            # Extract alert info
            severity = alert_data.get('severity', 'unknown')
            attack_type = alert_data.get('attack_type', 'unknown')
            attacker_ips = alert_data.get('attacker_ips', [])
            flow_count = alert_data.get('flow_count', 0)
            metrics = alert_data.get('metrics', {})
            
            logger.info(f"📨 Processing alert: {severity} - {len(attacker_ips)} IPs")
            
            # Process each attacker IP
            for ip in attacker_ips:
                # Check if whitelisted
                if self.redis_client.sismember(REDIS_KEY_WHITELIST, ip):
                    logger.debug(f"IP {ip} is whitelisted, skipping")
                    continue
                
                # Get existing metadata or create new
                metadata = self._get_ip_metadata(ip)
                
                if metadata:
                    # Update existing
                    metadata.last_seen = datetime.now().isoformat()
                    metadata.alert_count += 1
                    metadata.flow_count += flow_count
                    
                    # Update severity if more critical
                    severity_order = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
                    if severity_order.get(severity, 0) > severity_order.get(metadata.severity, 0):
                        metadata.severity = severity
                else:
                    # Create new metadata
                    metadata = IPMetadata(
                        ip=ip,
                        severity=severity,
                        attack_type=attack_type,
                        flow_count=flow_count,
                        confidence=metrics.get('suspicious_ratio', 0.0),
                        first_seen=datetime.now().isoformat(),
                        last_seen=datetime.now().isoformat(),
                        block_status='pending',
                        block_duration=DEFAULT_BLOCK_DURATION,
                        alert_count=1
                    )
                    
                    # Add to pending set
                    self.redis_client.sadd(REDIS_KEY_PENDING, ip)
                
                # Save metadata
                self._save_ip_metadata(metadata)
                
                logger.info(f"💾 Saved metadata for IP {ip}: {metadata.severity} (alerts: {metadata.alert_count})")
                
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
    
    def consume_alerts(self):
        """
        Consume alerts from Kafka (runs in background thread)
        """
        logger.info("Starting Kafka consumer...")
        
        try:
            for message in self.consumer:
                alert_data = message.value
                self.process_alert(alert_data)
                
        except KeyboardInterrupt:
            logger.info("Stopping Kafka consumer...")
        finally:
            self.consumer.close()
    
    def run(self):
        """
        Run Response Manager
        - Start Kafka consumer in background thread
        - Start Flask API server
        """
        # Start Kafka consumer thread
        consumer_thread = threading.Thread(target=self.consume_alerts, daemon=True)
        consumer_thread.start()
        logger.info("Kafka consumer thread started")
        
        # Start Flask API
        logger.info(f"Starting API server on port {API_PORT}")
        self.app.run(host='0.0.0.0', port=API_PORT, debug=False)

def main():
    logger.info("🚀 Starting DDoS Response Manager...")
    manager = ResponseManager()
    manager.run()

if __name__ == "__main__":
    main()
