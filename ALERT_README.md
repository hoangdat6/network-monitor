# 🚨 Alert System - README

## 📌 Tóm tắt

Tài liệu này giải đáp 2 câu hỏi chính về alert system:

1. **Tại sao alerts có trong Kafka topic nhưng không được gửi qua Telegram và không thống kê trên Grafana?**
2. **Tại sao AGG-008 (Distributed Attack) luôn trigger trước AGG-001 (SYN Flood) và AGG-002 (UDP Flood)?**

---

## 🎯 Câu trả lời nhanh

### Câu hỏi 1: Alerts không được gửi?

**Nguyên nhân:** Anti-spam mechanism đang hoạt động đúng như thiết kế

**Thống kê hiện tại:**
- 📥 Alerts nhận được: **14**
- ✅ Alerts đã gửi: **7**
- ⚠️ Alerts bị suppress: **7** (50%)
- 📊 Alerts được gộp: **7**

**Lý do suppress:** `MIN_ALERT_INTERVAL=60s` - Alerts đến quá nhanh (< 60 giây)

**Giải pháp:**
```bash
# Xem hướng dẫn chi tiết
cat ALERT_TROUBLESHOOTING.md

# Hoặc điều chỉnh ngay:
# 1. Edit src/docker-compose.monitoring.yml
# 2. Giảm MIN_ALERT_INTERVAL từ 60 → 30
# 3. docker restart telegram-notifier
```

### Câu hỏi 2: Tại sao AGG-008 trigger trước?

**Nguyên nhân:** Threshold của AGG-008 thấp nhất và dễ đạt được

**So sánh thresholds:**
| Rule | Threshold | Thời gian trigger |
|------|-----------|-------------------|
| AGG-008 | 200 unique IPs | ⚡ 5-10 giây |
| AGG-002 | 10,000 UDP packets | 🕐 20-30 giây |
| AGG-001 | 500 SYN packets | 🕐 15-25 giây |

**Giải pháp:**
```bash
# Xem giải thích chi tiết
cat WHY_AGG008_TRIGGERS_FIRST.md

# Hoặc test từng rule riêng:
./test_individual_rules.sh
```

---

## 📚 Tài liệu

| File | Mô tả | Độ ưu tiên |
|------|-------|-----------|
| **ALERT_SYSTEM_GUIDE.md** | 📖 Hướng dẫn tổng quan về alert system | ⭐⭐⭐ Đọc đầu tiên |
| **ALERT_TROUBLESHOOTING.md** | 🔧 Troubleshoot alerts không được gửi | ⭐⭐⭐ Quan trọng |
| **WHY_AGG008_TRIGGERS_FIRST.md** | 💡 Giải thích AGG-008 trigger trước | ⭐⭐ Nên đọc |

---

## 🛠️ Tools

| Script | Mô tả | Cách dùng |
|--------|-------|-----------|
| **check_alerts.sh** | Kiểm tra trạng thái alert system | `./check_alerts.sh` |
| **test_individual_rules.sh** | Test từng rule riêng biệt | `./test_individual_rules.sh` |

---

## 🚀 Quick Start

### 1. Kiểm tra trạng thái hiện tại

```bash
./check_alerts.sh
```

**Output mẫu:**
```
✓ ids_rule_detector is running
✓ telegram-notifier is running
✓ prometheus is running
✓ grafana is running

📥 Alerts Received:   14
✅ Alerts Sent:       7
⚠️  Alerts Suppressed: 7

⚠️  Alert Suppression Rate: 50.0%

Recommendations:
  1. Consider reducing MIN_ALERT_INTERVAL (current: 60s)
  2. Consider increasing MAX_ALERTS_PER_WINDOW (current: 5)
```

### 2. Điều chỉnh anti-spam settings (nếu cần)

```bash
# Edit configuration
nano src/docker-compose.monitoring.yml

# Tìm section telegram-notifier và sửa:
- MIN_ALERT_INTERVAL=30           # Giảm từ 60 → 30
- MAX_ALERTS_PER_WINDOW=10        # Tăng từ 5 → 10

# Apply changes
docker restart telegram-notifier

# Verify
docker logs -f telegram-notifier
```

### 3. Test từng rule riêng biệt

```bash
./test_individual_rules.sh
```

**Menu:**
```
1) AGG-001 (SYN Flood) - WITHOUT triggering AGG-008
2) AGG-002 (UDP Flood) - WITHOUT triggering AGG-008
3) AGG-008 (Distributed Attack) - ONLY this rule
4) Full attack (triggers multiple rules)
5) View current rule thresholds
6) Exit
```

### 4. Monitor alerts real-time

```bash
# Xem alerts từ detector
docker logs -f ids_rule_detector | grep ALERT

# Xem alerts từ telegram notifier
docker logs -f telegram-notifier | grep -E "(Sent:|Suppressed:)"

# Hoặc dùng script
./check_alerts.sh
```

### 5. Xem dashboard trong Grafana

```bash
# Mở browser
http://localhost:3000

# Login
Username: admin
Password: admin

# Navigate to
Dashboards → Rule-Based DDoS Detector
```

---

## 🔍 Deep Dive

### Alert Flow Pipeline

```
Network Traffic
    ↓
Flow Processor
    ↓
Kafka: network-flows
    ↓
Rule-Based Detector ← Kiểm tra rules
    ├─ Per-flow rules (fast)
    └─ Aggregation rules (window-based)
        ↓
Kafka: ddos-alerts ← Alerts được tạo ✅
    ↓
Telegram Notifier ← Anti-spam check
    ├─ Send (if allowed) ✅
    └─ Suppress (if too fast) ⚠️
        ↓
    Aggregate → Summary 📊
        ↓
Telegram Message
    ↓
Prometheus Metrics
    ↓
Grafana Dashboard
```

### Tại sao có Anti-Spam?

**Vấn đề:** Không có anti-spam → Spam Telegram với hàng trăm messages

**Ví dụ:**
```
11:28:00 - 🚨 UDP Flood detected
11:28:01 - 🚨 UDP Flood detected
11:28:02 - 🚨 UDP Flood detected
11:28:03 - 🚨 UDP Flood detected
... (100 messages trong 2 phút) ❌
```

**Giải pháp:** Anti-spam mechanism
```
11:28:00 - 🚨 UDP Flood detected ✅
11:28:01 - (suppressed)
11:28:02 - (suppressed)
...
11:31:00 - 📊 Summary: 50 alerts in 3 minutes ✅
```

### Tại sao AGG-008 trigger trước?

**Script tấn công của bạn:**
```python
for i in range(50000):  # 50k packets
    src_ip = random_ip()  # Mỗi packet từ IP khác nhau
    send_udp(src_ip, target)
```

**Kết quả:**
- Sau 5 giây: 200+ unique IPs → **AGG-008 trigger** ✅
- Sau 30 giây: 10,000+ UDP packets → **AGG-002 trigger** ✅

**Đây là thiết kế đúng đắn:**
- AGG-008 = Early warning (phát hiện sớm)
- AGG-002 = Attack confirmation (xác nhận tấn công)

---

## 📊 Current Status

### System Health

```bash
# Quick check
docker ps | grep -E "(telegram|detector|prometheus|grafana)"

# Expected output:
telegram-notifier   Up X minutes (healthy)
ids_rule_detector   Up X minutes (healthy)
prometheus          Up X minutes
grafana             Up X minutes
```

### Metrics Summary

**Rule-Based Detector:**
- Total Alerts: 22
- AGG-001 (SYN Flood): 1
- AGG-002 (UDP Flood): 10
- AGG-008 (Distributed): 7
- Others: 4

**Telegram Notifier:**
- Received: 14
- Sent: 7 (50%)
- Suppressed: 7 (50%)
- Reason: min_interval

**Grafana:**
- Status: ✅ Running
- Datasource: ✅ Connected
- Dashboard: ✅ Available

---

## ⚙️ Configuration Files

### Anti-Spam Settings
**File:** `src/docker-compose.monitoring.yml`
```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=60      # ← Điều chỉnh ở đây
    - MAX_ALERTS_PER_WINDOW=5    # ← Hoặc ở đây
```

### Rule Thresholds
**File:** `src/infra/rule-based-detector/rules.yaml`
```yaml
- id: "AGG-008"
  conditions:
    - metric: "unique_src_ips"
      value: 200  # ← Điều chỉnh ở đây để tránh trigger sớm
```

---

## 🎓 Learning Resources

### Hiểu về Rules

**AGG-001 (SYN Flood):**
- Phát hiện: High SYN count với low ACK ratio
- Threshold: 500 SYN packets, ratio > 0.8
- Window: 30 giây

**AGG-002 (UDP Flood):**
- Phát hiện: Massive UDP packet flood
- Threshold: 10,000 UDP packets
- Window: 60 giây

**AGG-008 (Distributed Attack):**
- Phát hiện: Many sources, low packets each
- Threshold: 200 unique IPs, < 10 flows/IP
- Window: 60 giây

### Best Practices

1. **Monitoring:**
   - Check `./check_alerts.sh` hàng ngày
   - Review Grafana dashboard hàng tuần
   - Analyze suppression rate hàng tháng

2. **Tuning:**
   - Start conservative (ít false positives)
   - Monitor 1-2 tuần
   - Adjust dựa trên thực tế

3. **Testing:**
   - Test từng rule riêng biệt
   - Verify trong Grafana
   - Document kết quả

---

## 🐛 Common Issues

### Issue 1: Alerts bị suppress quá nhiều

**Symptom:** Suppression rate > 50%

**Solution:**
```bash
# Option 1: Giảm MIN_ALERT_INTERVAL
MIN_ALERT_INTERVAL=30  # từ 60 → 30

# Option 2: Tăng MAX_ALERTS_PER_WINDOW
MAX_ALERTS_PER_WINDOW=10  # từ 5 → 10
```

### Issue 2: AGG-008 trigger quá sớm

**Symptom:** Mỗi lần test đều thấy AGG-008 trước

**Solution:**
```bash
# Option 1: Test với ít IPs hơn
./test_individual_rules.sh
# → Chọn option 1 hoặc 2

# Option 2: Tăng threshold
# Edit rules.yaml: unique_src_ips từ 200 → 500
```

### Issue 3: Grafana không hiển thị

**Symptom:** Dashboard trống

**Solution:**
```bash
# 1. Check Prometheus
curl http://localhost:9099/api/v1/query?query=up

# 2. Restart Grafana
docker restart grafana

# 3. Refresh dashboard
# Grafana UI → Click refresh icon
```

---

## 📞 Support

### Diagnostic Bundle

```bash
# Collect all diagnostic info
mkdir -p diagnostics
./check_alerts.sh > diagnostics/status.txt
docker logs telegram-notifier --tail 200 > diagnostics/telegram.log
docker logs ids_rule_detector --tail 200 > diagnostics/detector.log
tar -czf diagnostics_$(date +%Y%m%d_%H%M%S).tar.gz diagnostics/
```

### Checklist

- [ ] Đã đọc ALERT_SYSTEM_GUIDE.md?
- [ ] Đã chạy ./check_alerts.sh?
- [ ] Đã kiểm tra logs?
- [ ] Đã verify trong Grafana?
- [ ] Đã test với ./test_individual_rules.sh?

---

## 📝 Summary

**Vấn đề của bạn:**
1. ✅ Alerts **ĐÃ được tạo** và **ĐÃ có trong Kafka**
2. ⚠️ Một số alerts **BỊ SUPPRESS** do anti-spam (50%)
3. 📊 Alerts bị suppress **ĐƯỢC GỘP** thành summary
4. ✅ Grafana **ĐANG hoạt động** và có thể xem metrics

**Không phải bug, mà là thiết kế:**
- Anti-spam để tránh spam Telegram
- AGG-008 trigger sớm để early warning
- Multiple layers of detection

**Next steps:**
1. Đọc `ALERT_SYSTEM_GUIDE.md` để hiểu đầy đủ
2. Chạy `./check_alerts.sh` để xem status
3. Điều chỉnh anti-spam settings nếu cần
4. Test với `./test_individual_rules.sh`

---

**Created:** 2025-12-20  
**Version:** 1.0  
**Author:** Network Monitor Team
