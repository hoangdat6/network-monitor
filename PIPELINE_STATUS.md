# 📊 DDoS Detection Pipeline - Current Status

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         NETWORK TRAFFIC                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 1: PACKET CAPTURE                                                 │
│  ┌────────────────────┐                                                  │
│  │  CICFlowMeter      │  ✅ Running (Healthy)                           │
│  │  - tcpdump         │  - Capture packets từ wlp1s0                    │
│  │  - Extract flows   │  - Rotate PCAP mỗi 60s                          │
│  │  - Generate CSV    │  - Output: /output/*.csv                        │
│  └────────────────────┘                                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ CSV files
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 2: DATA PROCESSING                                                │
│  ┌────────────────────┐                                                  │
│  │  Flow Processor    │  ✅ Running (Healthy)                           │
│  │  - Watch CSV       │  - Đọc CSV từ CICFlowMeter                      │
│  │  - Normalize data  │  - Filter local IPs                             │
│  │  - Stream to Kafka │  ⚠️  Issue: Read-only filesystem                │
│  └────────────────────┘                                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ Kafka topic: network-flows
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 3: MESSAGE QUEUE                                                  │
│  ┌────────────────────┐                                                  │
│  │  Kafka + Zookeeper │  ✅ Running (Healthy)                           │
│  │  - Topic: network- │  - Store flows for processing                   │
│  │    flows           │  - Enable multiple consumers                    │
│  └────────────────────┘                                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ Consume flows
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 4: ML DETECTION                                                   │
│  ┌────────────────────┐                                                  │
│  │  DDoS Detector     │  ❌ Exit 128 (Failed)                           │
│  │  - Random Forest   │  Issue: Model files path hoặc rules missing     │
│  │  - Sliding Window  │                                                  │
│  │  - Alert Engine    │                                                  │
│  └────────────────────┘                                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ Kafka topic: ddos-alerts
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Layer 5: ALERTING & RESPONSE                                            │
│  ┌────────────────────┐                                                  │
│  │  Alert Manager     │  ⏸️  Not implemented yet                        │
│  │  - Process alerts  │                                                  │
│  │  - Trigger actions │                                                  │
│  └────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Current Issues

### 🔴 Critical
1. **DDoS Detector (Exit 128)**
   - Container crashed
   - Likely: Model files không tìm thấy
   - Volume mapping: `../../models/ddos_detector` → `/models`

2. **Flow Processor (Read-only filesystem)**
   - Volume mounted as `:ro` (read-only)
   - Không thể delete processed CSV files
   - Files tích tụ trong `/output`

### 🟡 Warning
- CICFlowMeter sometimes fails to process PCAP files
- FutureWarning in pandas (minor)

## Working Components

✅ **Kafka Infrastructure**
- Zookeeper: Running
- Kafka: Running (Healthy)
- Topic: `network-flows` ready

✅ **Network Capture**
- tcpdump capturing packets
- CICFlowMeter extracting flows
- CSV generation working

✅ **Data Pipeline**
- Flow processor consuming CSVs
- Normalizing data
- Sending to Kafka (3 flows processed)

## Fixes Needed

### Fix 1: DDoS Detector Container
```bash
# Check model files exist
ls -lh v2/src/models/ddos_detector/

# Expected files:
# - rf_ddos_model.pkl
# - rf_scaler.pkl
# - rf_label_encoder.pkl
# - detection_rules.yaml (in detector dir)
```

### Fix 2: Flow Processor Volume
Change docker-compose.network.yml:
```yaml
volumes:
  - network_flows:/output  # Remove :ro flag
```

## Next Steps

1. Fix volume permissions
2. Check model files path
3. Restart ddos-detector
4. Monitor logs
5. Test end-to-end flow

## Monitoring Commands

```bash
# Check all services
docker-compose -f docker-compose.data-pipeline.yml ps
docker-compose -f docker-compose.network.yml ps

# Check logs
docker logs ids_cicflowmeter
docker logs ids_flow_processor
docker logs ids_ddos_detector

# Monitor Kafka
kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic network-flows --from-beginning

# Check metrics
curl http://localhost:8000/metrics
```
