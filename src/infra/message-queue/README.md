# Kafka Log Streaming Setup

## 🎯 Mục đích
Setup Kafka cluster hoàn chỉnh để stream logs từ tất cả các components trong network monitoring system.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Application   │    │  Fluent Bit  │    │     Kafka       │
│     Logs        │───▶│   Log        │───▶│    Topics       │
│                 │    │  Aggregator  │    │                 │
└─────────────────┘    └──────────────┘    └─────────────────┘
                                                    │
                                            ┌───────▼────────┐
                                            │  Stream        │
                                            │  Processing    │
                                            │  (Layer 4)     │
                                            └────────────────┘
```

## 🚀 Quick Start

### 1. Khởi động Kafka Cluster

```bash
cd src/infra/message-queue

# Khởi động toàn bộ cluster
./manage-kafka.sh start

# Kiểm tra health
./manage-kafka.sh health

# Xem logs
./manage-kafka.sh logs
```

### 2. Test Integration

```bash
# Chạy integration tests
python3 test_kafka_integration.py

# Hoặc chạy individual tests
./manage-kafka.sh test-produce network-flows "Test message"
./manage-kafka.sh test-consume network-flows
```

### 3. Access Web Interfaces

- **Kafka UI**: http://localhost:8080
- **Fluent Bit Metrics**: http://localhost:2020
- **Schema Registry**: http://localhost:8081

## 📋 Services Overview

### Core Services

| Service | Port | Purpose | Health Check |
|---------|------|---------|--------------|
| Zookeeper | 2181 | Kafka coordination | `nc localhost 2181` |
| Kafka | 9092 | Message broker | `kafka-topics --list` |
| Schema Registry | 8081 | Schema management | `curl http://localhost:8081/subjects` |
| Kafka UI | 8080 | Web interface | `curl http://localhost:8080` |
| Kafka Connect | 8083 | External integrations | `curl http://localhost:8083/connectors` |
| Fluent Bit | 2020 | Log aggregation | `curl http://localhost:2020` |

### Kafka Topics

| Topic | Partitions | Retention | Purpose |
|-------|------------|-----------|---------|
| `network-flows` | 6 | 7 days | Raw network flows từ CICFlowMeter |
| `processed-flows` | 6 | 3 days | Normalized network features |
| `stream-analytics` | 3 | 1 day | Windowed analytics results |
| `application-logs` | 3 | 3 days | Application và Nginx logs |
| `system-metrics` | 3 | 7 days | System và container metrics |
| `security-events` | 3 | 30 days | Security alerts và events |
| `ddos-alerts` | 3 | 30 days | DDoS detection alerts |
| `web-attack-alerts` | 3 | 30 days | Web attack detection |
| `anomaly-alerts` | 3 | 14 days | Statistical anomalies |
| `mitigation-actions` | 3 | 30 days | Response actions |
| `admin-notifications` | 1 | 90 days | Admin notifications |

## 🔧 Configuration

### Environment Variables

Copy và edit `.env` file:

```bash
cp .env.example .env
# Edit các settings theo environment
```

Key settings:
- `KAFKA_BROKERS`: Kafka broker addresses
- `LOG_LEVEL`: Logging verbosity
- `KAFKA_HEAP_SIZE`: Memory allocation
- `RETENTION_MS`: Data retention period

### Fluent Bit Configuration

File: `configs/fluent-bit/fluent-bit.conf`

- **Input sources**: Nginx logs, application logs, system logs, CSV flows
- **Filters**: Parsing, enrichment, routing
- **Outputs**: Multiple Kafka topics với compression

### Topic Configuration

File: `kafka_manager.py` - `TOPIC_CONFIGS`

Customize partitions, retention, compression theo use case.

## 🧪 Testing & Monitoring

### Manual Testing

```bash
# List topics
./manage-kafka.sh list-topics

# Create custom topic
./manage-kafka.sh create-topic my-topic 3 1

# Produce message
./manage-kafka.sh test-produce my-topic "Hello Kafka"

# Consume messages
./manage-kafka.sh test-consume my-topic

# Monitor cluster
./manage-kafka.sh monitor
```

### Integration Testing

```bash
# Full integration test
python3 test_kafka_integration.py

# Test specific component
python3 -c "
from kafka_manager import KafkaManager
manager = KafkaManager()
print('Health:', manager.health_check())
print('Topics:', manager.list_topics())
"
```

### Performance Testing

```bash
# Producer performance test
kafka-producer-perf-test --topic network-flows \
  --num-records 10000 \
  --record-size 1024 \
  --throughput 1000 \
  --producer-props bootstrap.servers=localhost:9092

# Consumer performance test  
kafka-consumer-perf-test --topic network-flows \
  --messages 10000 \
  --bootstrap-server localhost:9092
```

## 📊 Monitoring & Troubleshooting

### Health Checks

```bash
# Cluster health
./manage-kafka.sh health

# Individual service logs
./manage-kafka.sh logs kafka
./manage-kafka.sh logs fluent-bit
./manage-kafka.sh logs zookeeper
```

### Common Issues

**1. Kafka không start**
```bash
# Check ports
netstat -tlnp | grep :9092

# Check disk space
df -h

# Restart with cleanup
./manage-kafka.sh stop
docker system prune -f
./manage-kafka.sh start
```

**2. Topics không được tạo**
```bash
# Manual topic creation
docker exec network-monitor-kafka kafka-topics \
  --create --bootstrap-server localhost:9092 \
  --topic test-topic --partitions 3 --replication-factor 1
```

**3. Fluent Bit không gửi logs**
```bash
# Check Fluent Bit logs
docker logs network-monitor-fluent-bit

# Test input files
echo "test log" >> /tmp/test.log

# Check Fluent Bit metrics
curl http://localhost:2020/api/v1/metrics
```

**4. Consumer lag**
```bash
# Check consumer groups
docker exec network-monitor-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 --list

# Check lag
docker exec network-monitor-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group my-group --describe
```

### Performance Tuning

**Memory Settings**
```yaml
# docker-compose.yml
environment:
  KAFKA_HEAP_OPTS: "-Xmx2G -Xms2G"  # Tăng memory
  KAFKA_JVM_PERFORMANCE_OPTS: "-XX:+UseG1GC"
```

**Network Settings**
```yaml
environment:
  KAFKA_SOCKET_SEND_BUFFER_BYTES: 102400
  KAFKA_SOCKET_RECEIVE_BUFFER_BYTES: 102400
  KAFKA_NUM_NETWORK_THREADS: 8
```

**Disk Settings**
```yaml
volumes:
  - kafka-data:/var/lib/kafka/data:Z  # Add SELinux context
```

## 🚨 Production Checklist

- [ ] SSL/TLS encryption enabled
- [ ] Authentication configured
- [ ] Backup strategy implemented
- [ ] Monitoring alerts setup
- [ ] Resource limits configured
- [ ] Log rotation enabled
- [ ] Health check endpoints monitored
- [ ] Disaster recovery plan documented

## 🔗 Integration với Network Monitor

### Layer 2: Data Collection
```python
# Gửi network flows
from kafka_manager import MessageProducer
producer = MessageProducer('network-flows')
producer.send_message(flow_data)
```

### Layer 4: Data Processing
```python
# Stream processing
from kafka_manager import MessageConsumer
consumer = MessageConsumer(['processed-flows'])
for message in consumer.consume():
    process_flow(message.value)
```

### Layer 5: Detection
```python
# Alert publishing
producer = MessageProducer('ddos-alerts')
producer.send_message({
    'alert_type': 'ddos_detected',
    'severity': 'high',
    'timestamp': datetime.now().isoformat()
})
```

## 📚 Resources

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Fluent Bit Documentation](https://docs.fluentbit.io/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Kafka Performance Tuning](https://kafka.apache.org/documentation/#tuning)

## 🎯 Next Steps

1. **Start Kafka cluster**: `./manage-kafka.sh start`
2. **Run tests**: `python3 test_kafka_integration.py`
3. **Check Kafka UI**: http://localhost:8080
4. **Integrate với application logs**: Configure log paths
5. **Setup monitoring**: Add Prometheus metrics