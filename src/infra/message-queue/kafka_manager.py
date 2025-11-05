"""
Kafka Message Queue Configuration

Mục đích: 
- Reliable message streaming giữa các services
- Decoupling data producers và consumers  
- High throughput cho real-time processing

Tại sao Kafka:
- High throughput (millions messages/sec)
- Fault tolerance với replication
- Horizontal scalability
- Built-in partitioning
- Strong durability guarantees

Cách khác:
- RabbitMQ: Tốt cho complex routing, nhưng lower throughput
- Redis Streams: Nhanh nhưng ít mature
- Apache Pulsar: Modern nhưng ecosystem nhỏ hơn
- Direct HTTP: Không reliable, không buffer

Bản chất hoạt động:
1. Producers send messages to topics
2. Topics được chia thành partitions
3. Messages được replicated across brokers
4. Consumers read from partitions
5. Offset tracking cho exactly-once processing
"""

import os
import json
import logging
import time
from typing import List, Dict, Optional
from kafka.admin import KafkaAdminClient, NewTopic
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import TopicAlreadyExistsError, KafkaError
import signal
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KafkaManager:
    """
    Manage Kafka topics, producers, and consumers
    """
    
    # Topic configurations
    TOPIC_CONFIGS = {
        'network-flows': {
            'partitions': 3,
            'replication_factor': 1,
            'cleanup_policy': 'delete',
            'retention_ms': 7 * 24 * 60 * 60 * 1000,  # 7 days
            'segment_ms': 60 * 60 * 1000,  # 1 hour
            'max_message_bytes': 10 * 1024 * 1024,  # 10MB
        },
        'http-logs': {
            'partitions': 2,
            'replication_factor': 1,
            'cleanup_policy': 'delete',
            'retention_ms': 3 * 24 * 60 * 60 * 1000,  # 3 days
            'segment_ms': 30 * 60 * 1000,  # 30 minutes
        },
        'alerts': {
            'partitions': 1,
            'replication_factor': 1,
            'cleanup_policy': 'delete',
            'retention_ms': 30 * 24 * 60 * 60 * 1000,  # 30 days
            'segment_ms': 24 * 60 * 60 * 1000,  # 24 hours
        },
        'actions': {
            'partitions': 1,
            'replication_factor': 1,
            'cleanup_policy': 'delete',
            'retention_ms': 7 * 24 * 60 * 60 * 1000,  # 7 days
        },
        'metrics': {
            'partitions': 2,
            'replication_factor': 1,
            'cleanup_policy': 'delete',
            'retention_ms': 1 * 24 * 60 * 60 * 1000,  # 1 day
            'segment_ms': 60 * 60 * 1000,  # 1 hour
        }
    }
    
    def __init__(self, bootstrap_servers: List[str] = ['kafka:9092']):
        self.bootstrap_servers = bootstrap_servers
        
        # Initialize admin client
        self.admin_client = KafkaAdminClient(
            bootstrap_servers=bootstrap_servers,
            client_id='kafka-manager'
        )
        
        logger.info(f"KafkaManager initialized with servers: {bootstrap_servers}")
    
    def create_topics(self) -> bool:
        """
        Create all required topics with configurations
        """
        topics_to_create = []
        
        for topic_name, config in self.TOPIC_CONFIGS.items():
            topic = NewTopic(
                name=topic_name,
                num_partitions=config['partitions'],
                replication_factor=config['replication_factor'],
                topic_configs={
                    'cleanup.policy': config.get('cleanup_policy', 'delete'),
                    'retention.ms': str(config.get('retention_ms', 604800000)),
                    'segment.ms': str(config.get('segment_ms', 3600000)),
                    'max.message.bytes': str(config.get('max_message_bytes', 1048576))
                }
            )
            topics_to_create.append(topic)
        
        try:
            # Create topics
            future_results = self.admin_client.create_topics(topics_to_create)
            
            # Wait for results
            for topic_name, future in future_results.items():
                try:
                    future.result()
                    logger.info(f"Topic '{topic_name}' created successfully")
                except TopicAlreadyExistsError:
                    logger.info(f"Topic '{topic_name}' already exists")
                except Exception as e:
                    logger.error(f"Failed to create topic '{topic_name}': {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create topics: {e}")
            return False
    
    def list_topics(self) -> List[str]:
        """
        List all available topics
        """
        try:
            metadata = self.admin_client.list_topics()
            topics = list(metadata.topics.keys())
            logger.info(f"Available topics: {topics}")
            return topics
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []
    
    def get_topic_info(self, topic_name: str) -> Optional[Dict]:
        """
        Get detailed information about a topic
        """
        try:
            metadata = self.admin_client.describe_topics([topic_name])
            if topic_name in metadata:
                topic_info = {
                    'name': topic_name,
                    'partitions': len(metadata[topic_name].partitions),
                    'replication_factor': len(metadata[topic_name].partitions[0].replicas),
                    'partition_details': []
                }
                
                for partition in metadata[topic_name].partitions:
                    partition_info = {
                        'partition_id': partition.partition,
                        'leader': partition.leader,
                        'replicas': partition.replicas,
                        'isr': partition.isr
                    }
                    topic_info['partition_details'].append(partition_info)
                
                return topic_info
        except Exception as e:
            logger.error(f"Failed to get info for topic '{topic_name}': {e}")
            return None
    
    def health_check(self) -> Dict:
        """
        Check Kafka cluster health
        """
        try:
            # Check connectivity
            metadata = self.admin_client.list_topics(timeout=5)
            brokers = metadata.brokers
            
            # Check each topic
            topic_health = {}
            for topic_name in self.TOPIC_CONFIGS.keys():
                topic_info = self.get_topic_info(topic_name)
                topic_health[topic_name] = topic_info is not None
            
            return {
                'status': 'healthy' if len(brokers) > 0 else 'unhealthy',
                'brokers_count': len(brokers),
                'brokers': [f"{broker.host}:{broker.port}" for broker in brokers],
                'topics_healthy': topic_health,
                'total_topics': len(topic_health),
                'healthy_topics': sum(topic_health.values()),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }

class MessageProducer:
    """
    Enhanced Kafka producer với retry logic
    """
    
    def __init__(self, 
                 bootstrap_servers: List[str] = ['kafka:9092'],
                 client_id: str = 'network-monitor-producer'):
        
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            client_id=client_id,
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            # Performance settings
            batch_size=32768,  # 32KB batches
            linger_ms=100,     # Wait 100ms for batching
            compression_type='gzip',
            # Reliability settings
            acks='all',        # Wait for all replicas
            retries=5,
            retry_backoff_ms=1000,
            # Timeout settings
            request_timeout_ms=30000,
            delivery_timeout_ms=120000
        )
        
        logger.info(f"MessageProducer initialized: {client_id}")
    
    def send_message(self, 
                    topic: str, 
                    message: Dict, 
                    key: Optional[str] = None,
                    partition: Optional[int] = None) -> bool:
        """
        Send message to Kafka topic với error handling
        """
        try:
            future = self.producer.send(
                topic=topic,
                value=message,
                key=key,
                partition=partition
            )
            
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            
            logger.debug(f"Message sent to {topic}:{record_metadata.partition}:{record_metadata.offset}")
            return True
            
        except KafkaError as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return False
    
    def close(self):
        """
        Close producer gracefully
        """
        try:
            self.producer.flush(timeout=30)
            self.producer.close(timeout=30)
            logger.info("Producer closed successfully")
        except Exception as e:
            logger.error(f"Error closing producer: {e}")

class MessageConsumer:
    """
    Enhanced Kafka consumer với auto-commit và error handling
    """
    
    def __init__(self,
                 topics: List[str],
                 group_id: str,
                 bootstrap_servers: List[str] = ['kafka:9092'],
                 auto_offset_reset: str = 'latest'):
        
        self.topics = topics
        self.group_id = group_id
        
        self.consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            client_id=f"{group_id}-consumer",
            # Serialization
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            # Offset management
            auto_offset_reset=auto_offset_reset,
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            # Performance settings
            fetch_min_bytes=1024,      # Wait for at least 1KB
            fetch_max_wait_ms=500,     # Wait max 500ms
            max_partition_fetch_bytes=1048576,  # 1MB max per partition
            # Session settings
            session_timeout_ms=30000,
            heartbeat_interval_ms=3000
        )
        
        logger.info(f"MessageConsumer initialized: {group_id} -> {topics}")
    
    def consume_messages(self, callback_func, timeout_ms: int = 1000):
        """
        Consume messages và call callback function
        """
        try:
            while True:
                messages = self.consumer.poll(timeout_ms=timeout_ms)
                
                if not messages:
                    continue
                
                for topic_partition, records in messages.items():
                    for record in records:
                        try:
                            # Call callback function
                            callback_func({
                                'topic': record.topic,
                                'partition': record.partition,
                                'offset': record.offset,
                                'key': record.key,
                                'value': record.value,
                                'headers': record.headers,
                                'timestamp': record.timestamp
                            })
                            
                        except Exception as e:
                            logger.error(f"Error in callback function: {e}")
                            # Continue processing other messages
                            continue
                
        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            self.close()
    
    def close(self):
        """
        Close consumer gracefully
        """
        try:
            self.consumer.close()
            logger.info("Consumer closed successfully")
        except Exception as e:
            logger.error(f"Error closing consumer: {e}")

def init_kafka_infrastructure():
    """
    Initialize Kafka infrastructure (topics, etc.)
    """
    kafka_servers = os.getenv('KAFKA_SERVERS', 'kafka:9092').split(',')
    
    manager = KafkaManager(kafka_servers)
    
    # Wait for Kafka to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            health = manager.health_check()
            if health['status'] == 'healthy':
                logger.info("Kafka is ready")
                break
        except:
            pass
        
        if i < max_retries - 1:
            logger.info(f"Waiting for Kafka... ({i+1}/{max_retries})")
            time.sleep(10)
        else:
            logger.error("Kafka failed to start after maximum retries")
            return False
    
    # Create topics
    if manager.create_topics():
        logger.info("Kafka topics created successfully")
        return True
    else:
        logger.error("Failed to create Kafka topics")
        return False

def main():
    """
    Main function for Kafka management
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Kafka Manager')
    parser.add_argument('command', choices=['init', 'health', 'topics'])
    parser.add_argument('--servers', default='kafka:9092', help='Kafka servers')
    
    args = parser.parse_args()
    
    servers = args.servers.split(',')
    manager = KafkaManager(servers)
    
    if args.command == 'init':
        success = init_kafka_infrastructure()
        sys.exit(0 if success else 1)
    
    elif args.command == 'health':
        health = manager.health_check()
        print(json.dumps(health, indent=2))
        sys.exit(0 if health['status'] == 'healthy' else 1)
    
    elif args.command == 'topics':
        topics = manager.list_topics()
        for topic in topics:
            info = manager.get_topic_info(topic)
            if info:
                print(f"Topic: {topic}")
                print(f"  Partitions: {info['partitions']}")
                print(f"  Replication: {info['replication_factor']}")
                print()

if __name__ == "__main__":
    main()