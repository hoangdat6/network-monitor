# 📚 Alert System - Complete Guide

## 🎯 Tóm tắt nhanh

Bạn đã hỏi 2 câu hỏi chính:

### 1️⃣ **Tại sao alerts có trong topic nhưng không được gửi/thống kê?**

**Nguyên nhân:** Anti-spam mechanism đang hoạt động
- ⚠️ **50% alerts bị suppressed** do `MIN_ALERT_INTERVAL=60s`
- 📊 Alerts bị suppress được **gộp lại** thành summary
- ✅ Hệ thống hoạt động **đúng như thiết kế**

**Giải pháp:** Xem `ALERT_TROUBLESHOOTING.md`

### 2️⃣ **Tại sao AGG-008 luôn trigger trước AGG-001/002?**

**Nguyên nhân:** Threshold của AGG-008 thấp nhất và dễ đạt được
- AGG-008: Chỉ cần **200 unique IPs** → Trigger sau **5-10 giây**
- AGG-002: Cần **10,000 UDP packets** → Trigger sau **20-30 giây**
- AGG-001: Cần **500 SYN packets** → Trigger sau **15-25 giây**

**Giải pháp:** Xem `WHY_AGG008_TRIGGERS_FIRST.md`

---

## 📁 Tài liệu chi tiết

| File | Mô tả |
|------|-------|
| `ALERT_TROUBLESHOOTING.md` | Hướng dẫn troubleshoot alerts không được gửi |
| `WHY_AGG008_TRIGGERS_FIRST.md` | Giải thích tại sao AGG-008 trigger trước |
| `check_alerts.sh` | Script kiểm tra trạng thái alert system |
| `test_individual_rules.sh` | Script test từng rule riêng biệt |

---

## 🚀 Quick Start

### Kiểm tra trạng thái hệ thống

```bash
./check_alerts.sh
```

**Output:**
- ✅ Container status
- 📊 Alert metrics (received/sent/suppressed)
- 🎯 Rule-based detector stats
- 📈 Prometheus & Grafana status
- 💡 Recommendations

### Test từng rule riêng biệt

```bash
./test_individual_rules.sh
```

**Menu:**
1. Test AGG-001 (SYN Flood) - không trigger AGG-008
2. Test AGG-002 (UDP Flood) - không trigger AGG-008
3. Test AGG-008 (Distributed) - chỉ rule này
4. Full attack - trigger nhiều rules
5. Xem thresholds
6. Exit

---

## 🔧 Cấu hình quan trọng

### Anti-Spam Settings

**File:** `src/docker-compose.monitoring.yml`

```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=60      # Khoảng cách tối thiểu giữa 2 alerts
    - MAX_ALERTS_PER_WINDOW=5    # Tối đa 5 alerts trong 5 phút
    - RATE_LIMIT_WINDOW=300      # Window 5 phút
    - AGGREGATION_WINDOW=180     # Gộp alerts sau 3 phút
    - COOLDOWN_AFTER_BURST=600   # Cooldown 10 phút
```

**Khuyến nghị cho Production:**
```yaml
- MIN_ALERT_INTERVAL=30          # Giảm xuống 30s
- MAX_ALERTS_PER_WINDOW=10       # Tăng lên 10
- AGGREGATION_WINDOW=120         # Giảm xuống 2 phút
```

**Áp dụng thay đổi:**
```bash
docker restart telegram-notifier
```

### Rule Thresholds

**File:** `src/infra/rule-based-detector/rules.yaml`

**Các threshold quan trọng:**

| Rule | Metric | Threshold | Window |
|------|--------|-----------|--------|
| AGG-001 | syn_flag_count | > 500 | 30s |
| AGG-002 | udp_packet_count | > 10,000 | 60s |
| AGG-008 | unique_src_ips | > 200 | 60s |

**Để tránh AGG-008 trigger sớm:**
```yaml
- id: "AGG-008"
  conditions:
    - metric: "unique_src_ips"
      value: 500  # Tăng từ 200 → 500
```

**Áp dụng thay đổi:**
```bash
docker restart ids_rule_detector
```

---

## 📊 Monitoring

### Xem metrics real-time

```bash
# Telegram Notifier metrics
curl -s http://localhost:8005/metrics | grep telegram_alerts

# Rule-based Detector metrics
curl -s http://localhost:8002/metrics | grep rule_detector_alerts

# Prometheus query
curl -s 'http://localhost:9099/api/v1/query?query=rule_detector_alerts_total'
```

### Xem logs

```bash
# Telegram Notifier
docker logs -f telegram-notifier

# Rule-based Detector
docker logs -f ids_rule_detector | grep ALERT

# Cả hai cùng lúc
docker logs -f telegram-notifier 2>&1 | grep -E "(Sent:|Suppressed:)" &
docker logs -f ids_rule_detector 2>&1 | grep "ALERT"
```

### Grafana Dashboard

**URL:** http://localhost:3000/d/rule-based-detector

**Login:**
- Username: `admin`
- Password: `admin`

**Panels quan trọng:**
- 🚨 Active Alerts
- 📊 Flows Processed
- 🎯 Alerts by Severity
- 🔥 Alerts by Rule ID

---

## 🧪 Testing Scenarios

### Scenario 1: Test AGG-002 riêng (không có AGG-008)

```bash
cd src/scripts
python3 -m ddos_attacks udp-flood \
  --target 192.168.241.2 \
  --port 53 \
  --num-packets 50000 \
  --num-sources 150  # < 200 để tránh AGG-008
```

**Kết quả mong đợi:**
- ❌ AGG-008 không trigger
- ✅ AGG-002 trigger sau ~30-40 giây

### Scenario 2: Test AGG-001 riêng (không có AGG-008)

```bash
python3 -m ddos_attacks syn-flood \
  --target 192.168.241.2 \
  --port 80 \
  --num-packets 10000 \
  --num-sources 100  # < 200
```

**Kết quả mong đợi:**
- ❌ AGG-008 không trigger
- ✅ AGG-001 trigger sau ~20-30 giây

### Scenario 3: Test AGG-008 riêng

```bash
python3 -m ddos_attacks distributed \
  --target 192.168.241.2 \
  --num-packets 5000 \
  --num-sources 500  # > 200
```

**Kết quả mong đợi:**
- ✅ AGG-008 trigger sau ~5-10 giây
- ❌ AGG-001/002 không trigger (không đủ packets)

### Scenario 4: Full attack (trigger tất cả)

```bash
python3 -m ddos_attacks udp-flood \
  --target 192.168.241.2 \
  --port 53 \
  --num-packets 50000 \
  --num-sources 1000  # > 200
```

**Kết quả mong đợi:**
- ✅ AGG-008 trigger đầu tiên (~5-10s)
- ✅ AGG-002 trigger sau đó (~30-40s)

---

## 🐛 Troubleshooting

### Vấn đề 1: Alerts không được gửi qua Telegram

**Kiểm tra:**
```bash
# 1. Check metrics
curl -s http://localhost:8005/metrics | grep suppressed

# 2. Check logs
docker logs telegram-notifier --tail 50 | grep Suppressed
```

**Nguyên nhân thường gặp:**
- ⚠️ `min_interval` - Alerts đến quá nhanh
- ⚠️ `rate_limit` - Quá nhiều alerts trong window
- ⚠️ `cooldown` - Đang trong cooldown period

**Giải pháp:**
- Giảm `MIN_ALERT_INTERVAL`
- Tăng `MAX_ALERTS_PER_WINDOW`
- Xem alert summaries trong Telegram

### Vấn đề 2: Grafana không hiển thị metrics

**Kiểm tra:**
```bash
# 1. Test Prometheus
curl -s 'http://localhost:9099/api/v1/query?query=up{job="rule-based-detector"}'

# 2. Test Grafana datasource
curl -s -u admin:admin http://localhost:3000/api/datasources
```

**Giải pháp:**
```bash
# Restart services
docker restart prometheus
docker restart grafana

# Refresh dashboard
# Grafana UI → Dashboard → Refresh icon
```

### Vấn đề 3: AGG-008 luôn trigger trước

**Đây KHÔNG phải là bug!**

**Giải pháp:**
1. **Chấp nhận thiết kế** - Xem AGG-008 như early warning
2. **Tăng threshold** - Sửa `unique_src_ips` từ 200 → 500
3. **Test riêng** - Dùng `test_individual_rules.sh`

---

## 📈 Best Practices

### 1. Monitoring Strategy

**3-tier approach:**
```
Tier 1: Real-time alerts (Telegram)
  ↓
Tier 2: Metrics dashboard (Grafana)
  ↓
Tier 3: Historical analysis (Prometheus)
```

### 2. Alert Tuning

**Bắt đầu với:**
- Conservative thresholds (ít false positives)
- Moderate anti-spam settings
- Monitor trong 1-2 tuần

**Sau đó điều chỉnh:**
- Tăng/giảm thresholds dựa trên false positive rate
- Điều chỉnh anti-spam settings
- Thêm/bỏ rules nếu cần

### 3. Testing Workflow

```bash
# 1. Kiểm tra trạng thái
./check_alerts.sh

# 2. Test từng rule
./test_individual_rules.sh

# 3. Monitor kết quả
docker logs -f ids_rule_detector | grep ALERT

# 4. Verify trong Grafana
# http://localhost:3000
```

---

## 🎓 Hiểu về Alert Flow

### Complete Alert Pipeline

```
1. Network Traffic
   ↓
2. Flow Processor (captures packets)
   ↓
3. Kafka Topic: network-flows
   ↓
4. Rule-Based Detector
   ├─→ Per-flow rules (fast path)
   └─→ Aggregation rules (window-based)
       ↓
5. Kafka Topic: ddos-alerts
   ↓
6. Telegram Notifier
   ├─→ Anti-spam check
   ├─→ Send immediately (if allowed)
   └─→ Aggregate (if suppressed)
       ↓
7. Telegram Message
   ↓
8. Prometheus Metrics
   ↓
9. Grafana Dashboard
```

### Timeline Example (UDP Flood với 1000 IPs)

```
T=0s:    Attack starts
T=5s:    200+ unique IPs detected
         → AGG-008 TRIGGERED ✅
         → Sent to Telegram ✅
         
T=30s:   10,000+ UDP packets accumulated
         → AGG-002 TRIGGERED ✅
         → Suppressed (min_interval) ⚠️
         → Added to aggregation buffer
         
T=180s:  Aggregation window expires
         → Summary sent to Telegram 📊
```

---

## 🔗 Quick Links

### Documentation
- [Alert Troubleshooting](ALERT_TROUBLESHOOTING.md)
- [Why AGG-008 Triggers First](WHY_AGG008_TRIGGERS_FIRST.md)

### Tools
- [Check Alerts Script](check_alerts.sh)
- [Test Individual Rules](test_individual_rules.sh)

### Services
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9099
- Telegram Notifier Metrics: http://localhost:8005/metrics
- Rule Detector Metrics: http://localhost:8002/metrics

### Logs
```bash
docker logs -f telegram-notifier
docker logs -f ids_rule_detector
docker logs -f prometheus
docker logs -f grafana
```

---

## 💡 Tips & Tricks

### Tip 1: Xem alert history trong Kafka

```bash
docker exec ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic ddos-alerts \
  --from-beginning \
  --max-messages 10
```

### Tip 2: Export metrics cho analysis

```bash
# Export Telegram metrics
curl -s http://localhost:8005/metrics > telegram_metrics_$(date +%Y%m%d_%H%M%S).txt

# Export Detector metrics
curl -s http://localhost:8002/metrics > detector_metrics_$(date +%Y%m%d_%H%M%S).txt
```

### Tip 3: Quick health check

```bash
# One-liner để check tất cả
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(telegram|detector|prometheus|grafana)"
```

### Tip 4: Reset alert state

```bash
# Restart để clear cooldowns và buffers
docker restart telegram-notifier
docker restart ids_rule_detector
```

---

## 🆘 Cần trợ giúp?

### Collect diagnostic info

```bash
# Tạo diagnostic bundle
mkdir -p diagnostics
./check_alerts.sh > diagnostics/alert_status.txt
docker logs telegram-notifier --tail 200 > diagnostics/telegram.log
docker logs ids_rule_detector --tail 200 > diagnostics/detector.log
curl -s http://localhost:8005/metrics > diagnostics/telegram_metrics.txt
curl -s http://localhost:8002/metrics > diagnostics/detector_metrics.txt

# Compress
tar -czf diagnostics_$(date +%Y%m%d_%H%M%S).tar.gz diagnostics/
```

### Common issues checklist

- [ ] Containers đang chạy?
- [ ] Kafka topic có alerts?
- [ ] Telegram bot token đúng?
- [ ] Prometheus scraping metrics?
- [ ] Grafana datasource configured?
- [ ] Anti-spam settings hợp lý?
- [ ] Rule thresholds phù hợp?

---

**Last updated:** 2025-12-20
**Version:** 1.0
