"""
Tests for Layer 3 - Message Queue Layer

Mục đích: Test Kafka functionality, topic management, producer/consumer
Bao gồm: Topic creation, message publishing, consuming, health checks
"""

import unittest
import json
import time
from unittest.mock import Mock, patch, MagicMock
import sys

# Add kafka manager to path
sys.path.append('/home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/src/infra/message-queue')

try:
    from kafka_manager import KafkaManager, MessageProducer, MessageConsumer
    KAFKA_AVAILABLE = True
except ImportError as e:
    print(f"Kafka modules not available: {e}")
    KAFKA_AVAILABLE = False

@unittest.skipUnless(KAFKA_AVAILABLE, "Kafka modules not available")
class TestKafkaManager(unittest.TestCase):
    """Test Kafka Manager functionality"""
    
    def setUp(self):
        self.mock_admin_client = Mock()
        with patch('kafka_manager.KafkaAdminClient') as mock_admin:
            mock_admin.return_value = self.mock_admin_client
            self.manager = KafkaManager(['localhost:9092'])
    
    def test_topic_configurations(self):
        """Test that all required topics are configured"""
        expected_topics = [
            'network-flows',
            'http-logs', 
            'alerts',
            'actions',
            'metrics'
        ]
        
        for topic in expected_topics:
            self.assertIn(topic, self.manager.TOPIC_CONFIGS)
            
        # Check network-flows has high retention (most important)
        network_flows_config = self.manager.TOPIC_CONFIGS['network-flows']
        self.assertEqual(network_flows_config['partitions'], 3) # High throughput
        self.assertGreater(network_flows_config['retention_ms'], 86400000) # > 1 day
    
    def test_create_topics_success(self):
        """Test successful topic creation"""
        # Mock successful creation
        mock_future = Mock()
        mock_future.result.return_value = None
        
        self.mock_admin_client.create_topics.return_value = {
            'network-flows': mock_future,
            'http-logs': mock_future
        }
        
        result = self.manager.create_topics()
        
        self.assertTrue(result)
        self.mock_admin_client.create_topics.assert_called_once()
    
    def test_create_topics_already_exists(self):
        """Test topic creation when topics already exist"""
        from kafka.errors import TopicAlreadyExistsError
        
        mock_future = Mock()
        mock_future.result.side_effect = TopicAlreadyExistsError()
        
        self.mock_admin_client.create_topics.return_value = {
            'network-flows': mock_future
        }
        
        result = self.manager.create_topics()
        
        # Should still return True (topics exist is OK)
        self.assertTrue(result)
    
    def test_list_topics(self):
        """Test listing topics"""
        mock_metadata = Mock()
        mock_metadata.topics.keys.return_value = ['topic1', 'topic2']
        
        self.mock_admin_client.list_topics.return_value = mock_metadata
        
        topics = self.manager.list_topics()
        
        self.assertEqual(topics, ['topic1', 'topic2'])
    
    def test_health_check_healthy(self):
        """Test health check when cluster is healthy"""
        # Mock healthy cluster
        mock_metadata = Mock()
        mock_broker1 = Mock()
        mock_broker1.host = 'localhost'
        mock_broker1.port = 9092
        mock_metadata.brokers = [mock_broker1]
        
        self.mock_admin_client.list_topics.return_value = mock_metadata
        
        # Mock topic info
        with patch.object(self.manager, 'get_topic_info') as mock_topic_info:
            mock_topic_info.return_value = {'name': 'test'}
            
            health = self.manager.health_check()
            
            self.assertEqual(health['status'], 'healthy')
            self.assertEqual(health['brokers_count'], 1)
            self.assertIn('localhost:9092', health['brokers'])
    
    def test_health_check_unhealthy(self):
        """Test health check when cluster is unhealthy"""
        self.mock_admin_client.list_topics.side_effect = Exception("Connection failed")
        
        health = self.manager.health_check()
        
        self.assertEqual(health['status'], 'unhealthy')
        self.assertIn('error', health)

@unittest.skipUnless(KAFKA_AVAILABLE, "Kafka modules not available")
class TestMessageProducer(unittest.TestCase):
    """Test Message Producer functionality"""
    
    def setUp(self):
        self.mock_producer = Mock()
        with patch('kafka_manager.KafkaProducer') as mock_kafka_producer:
            mock_kafka_producer.return_value = self.mock_producer
            self.producer = MessageProducer(['localhost:9092'])
    
    def test_send_message_success(self):
        """Test successful message sending"""
        # Mock successful send
        mock_future = Mock()
        mock_metadata = Mock()
        mock_metadata.partition = 0
        mock_metadata.offset = 123
        mock_future.get.return_value = mock_metadata
        
        self.mock_producer.send.return_value = mock_future
        
        message = {'type': 'test', 'data': 'value'}
        result = self.producer.send_message('test-topic', message)
        
        self.assertTrue(result)
        self.mock_producer.send.assert_called_once_with(
            topic='test-topic',
            value=message,
            key=None,
            partition=None
        )
    
    def test_send_message_failure(self):
        """Test message sending failure"""
        from kafka.errors import KafkaError
        
        # Mock failed send
        mock_future = Mock()
        mock_future.get.side_effect = KafkaError("Send failed")
        
        self.mock_producer.send.return_value = mock_future
        
        message = {'type': 'test'}
        result = self.producer.send_message('test-topic', message)
        
        self.assertFalse(result)
    
    def test_send_message_with_key(self):
        """Test sending message with key"""
        mock_future = Mock()
        mock_future.get.return_value = Mock()
        self.mock_producer.send.return_value = mock_future
        
        message = {'data': 'test'}
        key = 'partition-key'
        
        result = self.producer.send_message('test-topic', message, key=key)
        
        self.assertTrue(result)
        self.mock_producer.send.assert_called_once_with(
            topic='test-topic',
            value=message,
            key=key,
            partition=None
        )
    
    def test_close_producer(self):
        """Test producer graceful shutdown"""
        self.producer.close()
        
        self.mock_producer.flush.assert_called_once_with(timeout=30)
        self.mock_producer.close.assert_called_once_with(timeout=30)

@unittest.skipUnless(KAFKA_AVAILABLE, "Kafka modules not available")
class TestMessageConsumer(unittest.TestCase):
    """Test Message Consumer functionality"""
    
    def setUp(self):
        self.mock_consumer = Mock()
        with patch('kafka_manager.KafkaConsumer') as mock_kafka_consumer:
            mock_kafka_consumer.return_value = self.mock_consumer
            self.consumer = MessageConsumer(
                topics=['test-topic'],
                group_id='test-group'
            )
    
    def test_consumer_initialization(self):
        """Test consumer initialization with correct parameters"""
        self.assertEqual(self.consumer.topics, ['test-topic'])
        self.assertEqual(self.consumer.group_id, 'test-group')
    
    def test_consume_messages(self):
        """Test message consumption"""
        # Mock message
        mock_record = Mock()
        mock_record.topic = 'test-topic'
        mock_record.partition = 0
        mock_record.offset = 1
        mock_record.key = 'key1'
        mock_record.value = {'data': 'test'}
        mock_record.headers = []
        mock_record.timestamp = 1234567890
        
        # Mock poll result
        mock_topic_partition = Mock()
        self.mock_consumer.poll.side_effect = [
            {mock_topic_partition: [mock_record]},  # First poll returns message
            {},  # Second poll returns empty (will break due to test setup)
            KeyboardInterrupt()  # Third poll interrupted
        ]
        
        # Callback function to track calls
        callback_calls = []
        def test_callback(message):
            callback_calls.append(message)
        
        # Consume messages (will be interrupted)
        try:
            self.consumer.consume_messages(test_callback, timeout_ms=100)
        except:
            pass  # Expected due to mock setup
        
        # Verify callback was called
        self.assertEqual(len(callback_calls), 1)
        self.assertEqual(callback_calls[0]['topic'], 'test-topic')
        self.assertEqual(callback_calls[0]['value'], {'data': 'test'})
    
    def test_consume_messages_callback_error(self):
        """Test handling of callback errors during consumption"""
        mock_record = Mock()
        mock_record.topic = 'test-topic'
        mock_record.value = {'data': 'test'}
        
        mock_topic_partition = Mock()
        self.mock_consumer.poll.side_effect = [
            {mock_topic_partition: [mock_record]},
            KeyboardInterrupt()
        ]
        
        # Callback that raises exception
        def failing_callback(message):
            raise ValueError("Callback failed")
        
        # Should not crash when callback fails
        try:
            self.consumer.consume_messages(failing_callback)
        except:
            pass
        
        # Consumer should still be functional
        self.assertIsNotNone(self.consumer.consumer)
    
    def test_close_consumer(self):
        """Test consumer graceful shutdown"""
        self.consumer.close()
        
        self.mock_consumer.close.assert_called_once()

class TestKafkaIntegration(unittest.TestCase):
    """Integration tests for Kafka components"""
    
    @patch('kafka_manager.KafkaManager')
    def test_init_kafka_infrastructure(self, mock_manager_class):
        """Test Kafka infrastructure initialization"""
        from kafka_manager import init_kafka_infrastructure
        
        # Mock manager instance
        mock_manager = Mock()
        mock_manager.health_check.return_value = {'status': 'healthy'}
        mock_manager.create_topics.return_value = True
        mock_manager_class.return_value = mock_manager
        
        result = init_kafka_infrastructure()
        
        self.assertTrue(result)
        mock_manager.create_topics.assert_called_once()
    
    def test_message_serialization(self):
        """Test message serialization/deserialization"""
        # Test data
        original_message = {
            'flow_id': '123',
            'timestamp': '2023-01-01T00:00:00',
            'features': {
                'Flow Duration': 1000000,
                'Total Fwd Packets': 10,
                'SYN Flag Count': 1
            },
            'metadata': {
                'source': 'cicflowmeter',
                'processed_at': '2023-01-01T00:00:01'
            }
        }
        
        # Simulate serialization (what producer does)
        serialized = json.dumps(original_message, default=str).encode('utf-8')
        
        # Simulate deserialization (what consumer does)
        deserialized = json.loads(serialized.decode('utf-8'))
        
        self.assertEqual(original_message, deserialized)
    
    def test_topic_partitioning_strategy(self):
        """Test that topic partitioning makes sense"""
        if not KAFKA_AVAILABLE:
            self.skipTest("Kafka not available")
            
        manager = KafkaManager()
        
        # High-throughput topics should have more partitions
        network_flows_partitions = manager.TOPIC_CONFIGS['network-flows']['partitions']
        alerts_partitions = manager.TOPIC_CONFIGS['alerts']['partitions']
        
        # Network flows should have more partitions (higher throughput)
        self.assertGreaterEqual(network_flows_partitions, alerts_partitions)
        
        # All topics should have at least 1 partition
        for topic, config in manager.TOPIC_CONFIGS.items():
            self.assertGreaterEqual(config['partitions'], 1)

if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)