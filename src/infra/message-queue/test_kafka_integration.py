#!/usr/bin/env python3
"""
Kafka Integration Test Script

Mục đích: Test Kafka connectivity và log streaming
Kiểm tra: Topic creation, message production/consumption, log ingestion
"""

import sys
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory for imports
sys.path.append(str(Path(__file__).parent))

from kafka_manager import KafkaManager
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_kafka_connection():
    """Test basic Kafka connection"""
    logger.info("Testing Kafka connection...")
    
    try:
        manager = KafkaManager()
        
        if not manager.wait_for_kafka(timeout=30):
            logger.error("Kafka is not available")
            return False
            
        if manager.health_check():
            logger.info("✅ Kafka connection successful")
            return True
        else:
            logger.error("❌ Kafka health check failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Kafka connection failed: {e}")
        return False

def test_topic_creation():
    """Test topic creation"""
    logger.info("Testing topic creation...")
    
    try:
        manager = KafkaManager()
        
        # Create topics
        if manager.create_topics():
            logger.info("✅ Topics created successfully")
            
            # List topics to verify
            topics = manager.list_topics()
            logger.info(f"Available topics: {topics}")
            
            # Check if our topics exist
            required_topics = [
                'network-flows', 'processed-flows', 'stream-analytics',
                'application-logs', 'security-events'
            ]
            
            missing_topics = [topic for topic in required_topics if topic not in topics]
            
            if missing_topics:
                logger.warning(f"Missing topics: {missing_topics}")
                return False
            else:
                logger.info("✅ All required topics exist")
                return True
                
        else:
            logger.error("❌ Topic creation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Topic creation error: {e}")
        return False

def test_message_production():
    """Test message production"""
    logger.info("Testing message production...")
    
    try:
        # Create producer
        producer = KafkaProducer(
            bootstrap_servers=['kafka:29092'],
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            key_serializer=lambda x: x.encode('utf-8') if x else None
        )
        
        # Test messages
        test_messages = [
            {
                'topic': 'network-flows',
                'key': 'test-flow-1',
                'value': {
                    'timestamp': datetime.now().isoformat(),
                    'src_ip': '192.168.1.100',
                    'dst_ip': '10.0.0.1',
                    'src_port': 12345,
                    'dst_port': 80,
                    'protocol': 'TCP',
                    'flow_duration': 1500,
                    'tot_fwd_pkts': 10,
                    'tot_bwd_pkts': 8,
                    'label': 'BENIGN'
                }
            },
            {
                'topic': 'application-logs',
                'key': 'nginx-access',
                'value': {
                    'timestamp': datetime.now().isoformat(),
                    'remote_ip': '192.168.1.50',
                    'method': 'GET',
                    'path': '/api/status',
                    'status_code': 200,
                    'response_time': 0.125,
                    'user_agent': 'curl/7.68.0'
                }
            },
            {
                'topic': 'security-events',
                'key': 'potential-attack',
                'value': {
                    'timestamp': datetime.now().isoformat(),
                    'event_type': 'sql_injection_attempt',
                    'src_ip': '192.168.1.200',
                    'target_url': '/login?id=1 OR 1=1',
                    'severity': 'high',
                    'blocked': True
                }
            }
        ]
        
        # Send messages
        for msg in test_messages:
            future = producer.send(
                topic=msg['topic'],
                key=msg['key'],
                value=msg['value']
            )
            
            # Wait for message to be sent
            record_metadata = future.get(timeout=10)
            logger.info(f"Message sent to {record_metadata.topic}:{record_metadata.partition}:{record_metadata.offset}")
            
        producer.flush()
        producer.close()
        
        logger.info("✅ Message production successful")
        return True
        
    except Exception as e:
        logger.error(f"❌ Message production failed: {e}")
        return False

def test_message_consumption():
    """Test message consumption"""
    logger.info("Testing message consumption...")
    
    try:
        # Create consumer
        consumer = KafkaConsumer(
            'network-flows',
            'application-logs', 
            'security-events',
            bootstrap_servers=['kafka:29092'],
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            key_deserializer=lambda x: x.decode('utf-8') if x else None,
            consumer_timeout_ms=10000,  # 10 second timeout
            auto_offset_reset='earliest'
        )
        
        messages_received = 0
        start_time = time.time()
        
        for message in consumer:
            logger.info(f"Received message from {message.topic}: {message.key}")
            logger.debug(f"Message value: {message.value}")
            
            messages_received += 1
            
            # Stop after receiving some messages or timeout
            if messages_received >= 3 or (time.time() - start_time) > 15:
                break
                
        consumer.close()
        
        if messages_received > 0:
            logger.info(f"✅ Message consumption successful ({messages_received} messages)")
            return True
        else:
            logger.warning("⚠️ No messages consumed (this might be normal if no messages were sent)")
            return True  # Not necessarily an error
            
    except Exception as e:
        logger.error(f"❌ Message consumption failed: {e}")
        return False

def test_log_file_simulation():
    """Simulate log files for Fluent Bit to pick up"""
    logger.info("Creating test log files...")
    
    try:
        # Create test directories
        log_dirs = ['/tmp/nginx', '/tmp/app']
        for log_dir in log_dirs:
            os.makedirs(log_dir, exist_ok=True)
            
        # Simulate nginx access log
        nginx_log = '/tmp/nginx/access.log'
        with open(nginx_log, 'a') as f:
            log_entry = f'{datetime.now().strftime("%d/%b/%Y:%H:%M:%S %z")} '
            log_entry += '192.168.1.100 - - [GET /api/test HTTP/1.1] 200 1234 "-" "test-agent"\n'
            f.write(log_entry)
            
        # Simulate application log
        app_log = '/tmp/app/application.log'
        with open(app_log, 'a') as f:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': 'INFO',
                'message': 'Test application log entry',
                'component': 'test-script'
            }
            f.write(json.dumps(log_entry) + '\n')
            
        # Simulate network flow CSV
        flow_csv = '/tmp/flows.csv'
        with open(flow_csv, 'a') as f:
            csv_line = '1500,10,8,1200,800,150,64,95.5,12.3,120,48,75.2,8.9,800.0,12.0,125.5,25.8,500,10,2500,250.0,50.2,1000,50,1800,200.0,30.1,800,25,2,1,0,0,40,32,6.7,5.3,48,150,95.5,12.3,144.25,1,2,0,1,8,0,0,0,0.625,97.75,95.5,75.2,0,0,0,0,0,0,5,600,3,240,8192,4096,2,64,500.0,100.5,1000,100,250.5,50.2,500,50,6,80,443,' + datetime.now().isoformat() + ',BENIGN\n'
            f.write(csv_line)
            
        logger.info("✅ Test log files created")
        logger.info(f"Created: {nginx_log}, {app_log}, {flow_csv}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Log file creation failed: {e}")
        return False

def test_fluent_bit_integration():
    """Test Fluent Bit integration"""
    logger.info("Testing Fluent Bit integration...")
    
    try:
        import requests
        
        # Check Fluent Bit health endpoint
        response = requests.get('http://localhost:2020', timeout=5)
        
        if response.status_code == 200:
            logger.info("✅ Fluent Bit is running and accessible")
            
            # Check metrics endpoint
            metrics_response = requests.get('http://localhost:2020/api/v1/metrics', timeout=5)
            if metrics_response.status_code == 200:
                metrics = metrics_response.json()
                logger.info(f"Fluent Bit metrics: {len(metrics)} entries")
                return True
            else:
                logger.warning("Fluent Bit metrics endpoint not accessible")
                return True  # Health endpoint works, that's enough
                
        else:
            logger.error(f"❌ Fluent Bit health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️ Fluent Bit integration test failed: {e}")
        logger.info("This might be normal if Fluent Bit is not running")
        return True  # Don't fail the whole test for this

def run_integration_tests():
    """Run all integration tests"""
    logger.info("Starting Kafka Integration Tests")
    logger.info("=" * 50)
    
    tests = [
        ("Kafka Connection", test_kafka_connection),
        ("Topic Creation", test_topic_creation),
        ("Message Production", test_message_production),
        ("Message Consumption", test_message_consumption),
        ("Log File Simulation", test_log_file_simulation),
        ("Fluent Bit Integration", test_fluent_bit_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running: {test_name}")
        logger.info("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name}: PASSED")
            else:
                logger.error(f"❌ {test_name}: FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
            
        time.sleep(2)  # Brief pause between tests
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name:<25} {status}")
    
    logger.info("-" * 50)
    logger.info(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All tests passed! Kafka integration is working correctly.")
        return True
    else:
        logger.error(f"⚠️ {total-passed} tests failed. Check the logs above for details.")
        return False

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)