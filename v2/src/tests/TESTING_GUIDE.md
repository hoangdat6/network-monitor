# DDoS Testing Guide

## 🎯 Cách Test DDoS Detection System

### Phương pháp 1: Python Script (Recommended)

**Advantages:**
- Cross-platform (Windows/Linux/Mac)
- Nhiều loại attack patterns
- Control tốt tốc độ và duration
- Multi-threaded support

**Usage:**
```bash
cd v2/src/tests

# SYN Flood - 30 giây
python test_ddos.py --target 192.168.1.200 --type syn --duration 30

# HTTP Flood - 200 requests/giây
python test_ddos.py --target 192.168.1.200 --port 80 --type http --rate 200 --duration 30

# UDP Flood - packets lớn
python test_ddos.py --target 192.168.1.200 --type udp --packet-size 2048 --duration 30

# Slowloris - 100 connections
python test_ddos.py --target 192.168.1.200 --port 80 --type slowloris --connections 100 --duration 60

# Multi-threaded (10 threads)
python test_ddos.py --target 192.168.1.200 --type syn --threads 10 --duration 30
```

### Phương pháp 2: hping3 (Linux only)

**Advantages:**
- Tốc độ cực cao (flood mode)
- Low-level packet crafting
- Built-in random source IPs

**Installation:**
```bash
sudo apt-get install hping3
```

**Usage:**
```bash
cd v2/src/tests
chmod +x quick_test.sh

# Interactive menu
./quick_test.sh 192.168.1.200 80 30
```

**Manual hping3 commands:**
```bash
# SYN Flood
sudo hping3 -S -p 80 --flood --rand-source 192.168.1.200

# UDP Flood  
sudo hping3 --udp -p 80 --flood --rand-source 192.168.1.200

# ICMP Flood
sudo hping3 --icmp --flood --rand-source 192.168.1.200

# Controlled rate (100 packets/s)
sudo hping3 -S -p 80 --faster --rand-source 192.168.1.200
```

### Phương pháp 3: Apache Bench (ab)

**For HTTP flood testing:**
```bash
# 10,000 requests, 100 concurrent
ab -n 10000 -c 100 http://192.168.1.200/

# Unlimited requests for 30 seconds
ab -t 30 -c 100 http://192.168.1.200/
```

### Phương pháp 4: Vegeta (HTTP Load Testing)

**Installation:**
```bash
go install github.com/tsenart/vegeta@latest
```

**Usage:**
```bash
# 1000 requests/second for 30 seconds
echo "GET http://192.168.1.200/" | vegeta attack -rate=1000 -duration=30s | vegeta report
```

---

## 📊 Monitoring During Test

### 1. Watch DDoS Detector Logs
```bash
# Real-time logs
docker logs -f ids_ddos_detector

# Look for:
# - "Suspicious flow" messages
# - "🚨 DDoS ALERT" warnings
```

### 2. Check Kafka Alerts
```bash
# Terminal 1: Watch alerts
kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic ddos-alerts --from-beginning

# Expected output:
# {
#   "alert_id": "ddos_1732147200",
#   "severity": "high",
#   "flow_count": 150,
#   "attacker_ips": ["1.2.3.4", "5.6.7.8"],
#   ...
# }
```

### 3. Check Prometheus Metrics
```bash
# Total flows processed
curl http://localhost:8001/metrics | grep ddos_flows_processed_total

# Suspicious flows by type
curl http://localhost:8001/metrics | grep ddos_flows_suspicious_total

# Alerts triggered
curl http://localhost:8001/metrics | grep ddos_alerts_triggered_total

# Active attackers
curl http://localhost:8001/metrics | grep ddos_active_attackers
```

### 4. Monitor Network Traffic
```bash
# Watch captured flows
docker exec -it ids_cicflowmeter ls -lh /output/

# Check flow processor logs
docker logs -f ids_flow_processor | grep "Successfully processed"
```

---

## 🧪 Test Scenarios

### Scenario 1: Low Severity Alert
**Goal**: Trigger low severity alert (10+ suspicious flows, 30% ratio)

```bash
# Gentle attack - should trigger LOW alert
python test_ddos.py --target 192.168.1.200 --type http --rate 50 --duration 20
```

**Expected**:
- Alert severity: `low`
- Recommendation: "Monitor the situation"

### Scenario 2: Medium Severity Alert
**Goal**: Trigger medium severity (50+ flows, 50% ratio)

```bash
# Moderate attack - should trigger MEDIUM alert
python test_ddos.py --target 192.168.1.200 --type syn --duration 30 --threads 3
```

**Expected**:
- Alert severity: `medium`
- Recommendation: "Apply rate limiting"

### Scenario 3: High Severity Alert
**Goal**: Trigger high severity (100+ flows, 70% ratio)

```bash
# Aggressive attack - should trigger HIGH alert
python test_ddos.py --target 192.168.1.200 --type syn --duration 30 --threads 5
```

**Expected**:
- Alert severity: `high`
- Recommendation: "Block attacking IPs immediately"

### Scenario 4: Critical Alert
**Goal**: Trigger critical alert (200+ flows, 80% ratio)

```bash
# Massive attack - should trigger CRITICAL alert
python test_ddos.py --target 192.168.1.200 --type syn --duration 60 --threads 10
```

**Expected**:
- Alert severity: `critical`
- Recommendation: "EMERGENCY: Activate all DDoS countermeasures"

---

## 🔍 Verification Checklist

After running test:

- [ ] CICFlowMeter captured packets → Check logs
- [ ] Flow Processor sent flows to Kafka → Check logs
- [ ] DDoS Detector received flows → Check "Suspicious flow" messages
- [ ] Sliding windows accumulated flows → Check metrics `ddos_flows_in_window`
- [ ] Alert threshold exceeded → Check for "🚨 DDoS ALERT"
- [ ] Alert sent to Kafka → Check `ddos-alerts` topic
- [ ] Correct severity level → Verify against thresholds
- [ ] Attacker IPs identified → Check alert content
- [ ] Metrics updated → Check Prometheus metrics

---

## ⚙️ Tuning for Testing

### Make Detection More Sensitive (for testing)
Edit `v2/src/detection/ddos-detector/detection_rules.yaml`:

```yaml
thresholds:
  low:
    min_flows: 5              # Lower from 10
    min_suspicious_ratio: 0.2  # Lower from 0.3
    min_confidence: 0.5        # Lower from 0.6
```

Then restart:
```bash
docker restart ids_ddos_detector
```

### Increase Attack Intensity
```bash
# More threads
python test_ddos.py --target 192.168.1.200 --type syn --threads 20

# Higher rate
python test_ddos.py --target 192.168.1.200 --type http --rate 500

# Longer duration
python test_ddos.py --target 192.168.1.200 --type udp --duration 120
```

---

## 🚨 Troubleshooting

### No alerts triggered?
1. Check detector is processing flows:
   ```bash
   docker logs ids_ddos_detector | grep "Suspicious flow"
   ```

2. Lower thresholds in `detection_rules.yaml`

3. Verify flows reaching Kafka:
   ```bash
   kafka-console-consumer.sh --bootstrap-server localhost:9092 \
     --topic network-flows --max-messages 10
   ```

### False positives?
1. Add your test IPs to whitelist in `detection_rules.yaml`:
   ```yaml
   ip_filtering:
     whitelist:
       - 192.168.1.50  # Your test machine
   ```

2. Increase thresholds

### Permission denied errors?
```bash
# For hping3
sudo ./quick_test.sh

# For Python script with raw sockets
sudo python test_ddos.py ...
```

---

## 📚 Best Practices

1. **Test in isolation**: Stop other network-heavy applications
2. **Use local network**: Test against local server, not production
3. **Start small**: Begin with low-intensity tests
4. **Monitor resources**: Watch CPU/memory during test
5. **Clean up**: Stop attack immediately if issues occur (Ctrl+C)
6. **Document results**: Record which attacks triggered which alerts
7. **Tune gradually**: Adjust thresholds based on results

---

## 🎓 Understanding Results

### Normal Behavior
- Most flows classified as BENIGN
- Occasional suspicious flows (false positives OK)
- No alerts if below threshold

### During Attack
- Many flows classified as DDoS
- High suspicious ratio (>50%)
- Alert triggered within 10-60 seconds
- Metrics show spike in `ddos_flows_suspicious_total`

### After Attack
- Flows drop back to normal
- Alert cooldown prevents spam (5 minutes default)
- Windows clear old flows automatically
- System returns to monitoring state

---

## 📞 Support

If detection not working:
1. Check all containers running: `docker ps`
2. Review logs: `docker logs <container>`
3. Verify Kafka connectivity
4. Test with simpler attacks first (HTTP flood)
5. Check firewall not blocking traffic
