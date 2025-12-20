# 🔧 Alert Troubleshooting Guide

## 📋 Tóm tắt vấn đề

Bạn đã phát hiện rằng mặc dù alerts đã có trong Kafka topic `ddos-alerts`, nhưng:
1. ❌ Một số alerts **không được gửi qua Telegram**
2. ❓ Alerts **có thể không hiển thị đúng trên Grafana**

---

## 🔍 Nguyên nhân chính

### 1. ⚠️ **Anti-Spam Mechanism đang hoạt động**

Telegram Notifier có cơ chế **chống spam** để tránh gửi quá nhiều alerts:

**Cấu hình hiện tại:**
```yaml
RATE_LIMIT_WINDOW: 300 giây (5 phút)
MAX_ALERTS_PER_WINDOW: 5 alerts
MIN_ALERT_INTERVAL: 60 giây
AGGREGATION_WINDOW: 180 giây (3 phút)
COOLDOWN_AFTER_BURST: 600 giây (10 phút)
```

**Cách hoạt động:**
- Nếu 2 alerts đến **cách nhau < 60 giây** → Alert thứ 2 bị **SUPPRESSED**
- Nếu có **> 5 alerts trong 5 phút** → Kích hoạt **COOLDOWN mode**
- Alerts bị suppress sẽ được **gộp lại** và gửi dưới dạng **summary**

**Ví dụ từ logs của bạn:**
```
2025-12-20 11:28:06 - Sent: rule_AGG-008_1766230086 ✅
2025-12-20 11:28:07 - Suppressed: rule_AGG-001_1766230087 ❌ (min_interval)
```
→ Alert `AGG-001` đến chỉ **1 giây** sau alert `AGG-008`, nên bị suppress!

**Thống kê từ Prometheus:**
```
Alerts received: 14 (5 high + 9 critical)
Alerts sent: 7 (5 high + 2 critical)
Alerts suppressed: 7 (do min_interval)
Alerts aggregated: 7
```

### 2. 📊 **Grafana Dashboard**

**Tình trạng:**
- ✅ Prometheus **đang scrape metrics** từ rule-based-detector thành công
- ✅ Grafana **có thể kết nối** với Prometheus
- ✅ Metrics **đang có sẵn** trong Prometheus

**Kiểm tra:**
```bash
# Kiểm tra metrics trong Prometheus
curl -s 'http://localhost:9099/api/v1/query?query=rule_detector_alerts_total' | python3 -m json.tool

# Kết quả:
# AGG-001: 1 alert
# AGG-002: 10 alerts
# AGG-004: 1 alert
# AGG-006: 1 alert
# AGG-008: 7 alerts
# AGG-009: 2 alerts
```

---

## 💡 Giải pháp

### **Giải pháp 1: Điều chỉnh Anti-Spam Settings** ⭐ (Khuyến nghị)

Tùy thuộc vào nhu cầu của bạn, có thể điều chỉnh các tham số:

#### **Option A: Giảm MIN_ALERT_INTERVAL** (Nhận nhiều alerts hơn)

**File:** `src/docker-compose.monitoring.yml`

```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=30  # Giảm từ 60s → 30s
```

**Ưu điểm:**
- Nhận được nhiều alerts hơn
- Phản ứng nhanh hơn với các threats

**Nhược điểm:**
- Có thể bị spam nếu có nhiều attacks liên tiếp

#### **Option B: Tăng MAX_ALERTS_PER_WINDOW** (Tránh cooldown)

```yaml
telegram-notifier:
  environment:
    - MAX_ALERTS_PER_WINDOW=10  # Tăng từ 5 → 10
```

**Ưu điểm:**
- Ít khi bị cooldown
- Nhận được nhiều alerts trước khi chuyển sang aggregation mode

#### **Option C: Tắt hoàn toàn Anti-Spam** (Không khuyến nghị)

```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=0      # Tắt min interval
    - MAX_ALERTS_PER_WINDOW=999 # Tắt rate limit
```

**Cảnh báo:** Có thể bị spam rất nhiều messages!

#### **Cách áp dụng:**

```bash
# 1. Chỉnh sửa file
nano src/docker-compose.monitoring.yml

# 2. Restart telegram-notifier
docker restart telegram-notifier

# 3. Kiểm tra logs
docker logs -f telegram-notifier
```

---

### **Giải pháp 2: Sử dụng Alert Aggregation** (Đang hoạt động)

Hệ thống **đã tự động gộp** các alerts bị suppress:

**Cách hoạt động:**
1. Alerts bị suppress được lưu vào buffer
2. Khi đủ **10 alerts** hoặc sau **3 phút**, gửi **summary**
3. Summary bao gồm:
   - Tổng số alerts
   - Phân loại theo severity
   - Top attackers

**Kiểm tra summary:**
- Xem logs của telegram-notifier
- Tìm messages có tiêu đề "📊 ALERT SUMMARY"

---

### **Giải pháp 3: Kiểm tra và Refresh Grafana Dashboard**

#### **Bước 1: Kiểm tra Datasource**

```bash
# Test Prometheus connection từ Grafana
docker exec grafana sh -c 'wget -qO- "http://prometheus:9090/api/v1/query?query=up"'
```

#### **Bước 2: Refresh Dashboard**

1. Mở Grafana: http://localhost:3000
2. Login: `admin` / `admin`
3. Vào **Dashboards** → **Rule-Based DDoS Detector**
4. Click **Refresh** icon (⟳) ở góc phải trên
5. Hoặc thay đổi time range để force reload

#### **Bước 3: Kiểm tra Queries**

Nếu dashboard vẫn không hiển thị, kiểm tra queries:

```promql
# Query 1: Total alerts
sum(rule_detector_alerts_total)

# Query 2: Alerts by severity
rate(rule_detector_alerts_total{severity="critical"}[1m]) * 60

# Query 3: Alerts by rule
sum by (rule_id) (increase(rule_detector_alerts_total[5m]))
```

#### **Bước 4: Re-import Dashboard** (Nếu cần)

```bash
# Restart Grafana để reload dashboards
docker restart grafana

# Hoặc manually import dashboard
# 1. Copy nội dung file: src/configs/grafana/dashboards/rule-based-detector-dashboard.json
# 2. Grafana UI → Dashboards → Import → Paste JSON
```

---

## 🧪 Testing và Verification

### **Test 1: Kiểm tra Alerts trong Kafka**

```bash
# Xem alerts trong topic
docker exec ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic ddos-alerts \
  --from-beginning \
  --max-messages 5
```

### **Test 2: Kiểm tra Telegram Notifier Metrics**

```bash
# Xem metrics
curl -s http://localhost:8005/metrics | grep telegram_alerts

# Kết quả mong đợi:
# telegram_alerts_received_total{severity="high"} 5.0
# telegram_alerts_sent_total{severity="high"} 5.0
# telegram_alerts_suppressed_total{reason="min_interval"} 7.0
```

### **Test 3: Kiểm tra Prometheus Metrics**

```bash
# Query alerts từ Prometheus
curl -s 'http://localhost:9099/api/v1/query?query=rule_detector_alerts_total' \
  | python3 -m json.tool
```

### **Test 4: Kiểm tra Grafana Dashboard**

```bash
# Test datasource
curl -s -u admin:admin http://localhost:3000/api/datasources | python3 -m json.tool

# Kết quả mong đợi:
# - name: "Prometheus"
# - url: "http://prometheus:9090"
# - isDefault: true
```

---

## 📊 Monitoring và Debugging

### **Xem Logs Real-time**

```bash
# Telegram Notifier
docker logs -f telegram-notifier

# Rule-based Detector
docker logs -f ids_rule_detector

# Prometheus
docker logs -f prometheus

# Grafana
docker logs -f grafana
```

### **Kiểm tra Health Status**

```bash
# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check specific services
docker inspect telegram-notifier --format '{{.State.Health.Status}}'
docker inspect ids_rule_detector --format '{{.State.Health.Status}}'
```

### **Debug Queries trong Grafana**

1. Mở dashboard
2. Click vào panel cần debug
3. Click **Edit** (icon bút chì)
4. Tab **Query** → Click **Query inspector**
5. Xem **Response** để kiểm tra data

---

## 🎯 Khuyến nghị

### **Cho Production Environment:**

```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=30           # 30s - Balance giữa spam và responsiveness
    - MAX_ALERTS_PER_WINDOW=10        # 10 alerts - Tránh cooldown quá sớm
    - RATE_LIMIT_WINDOW=300           # 5 phút - Giữ nguyên
    - AGGREGATION_WINDOW=120          # 2 phút - Gửi summary nhanh hơn
    - COOLDOWN_AFTER_BURST=300        # 5 phút - Giảm cooldown time
```

### **Cho Testing/Development:**

```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=10           # 10s - Nhận alerts nhanh
    - MAX_ALERTS_PER_WINDOW=20        # 20 alerts - Ít khi cooldown
    - AGGREGATION_WINDOW=60           # 1 phút - Summary nhanh
```

### **Cho High-Security Environment:**

```yaml
telegram-notifier:
  environment:
    - MIN_ALERT_INTERVAL=0            # Không delay
    - MAX_ALERTS_PER_WINDOW=999       # Không limit
    # Chấp nhận spam để không bỏ lỡ alerts
```

---

## 📝 Tóm tắt

**Vấn đề của bạn:**
- ✅ Alerts **ĐÃ được tạo** bởi rule-based detector
- ✅ Alerts **ĐÃ được gửi** vào Kafka topic
- ⚠️ Một số alerts **BỊ SUPPRESS** bởi anti-spam mechanism
- ✅ Prometheus **ĐANG scrape** metrics thành công
- ✅ Grafana **CÓ THỂ kết nối** với Prometheus

**Giải pháp:**
1. **Điều chỉnh anti-spam settings** theo nhu cầu
2. **Kiểm tra alert summaries** trong Telegram
3. **Refresh Grafana dashboard** nếu cần

**Next Steps:**
1. Quyết định cấu hình anti-spam phù hợp
2. Restart telegram-notifier với config mới
3. Monitor và adjust theo thực tế

---

## 🆘 Liên hệ hỗ trợ

Nếu vẫn gặp vấn đề, cung cấp thông tin sau:

```bash
# 1. Logs
docker logs telegram-notifier --tail 100 > telegram-logs.txt
docker logs ids_rule_detector --tail 100 > detector-logs.txt

# 2. Metrics
curl -s http://localhost:8005/metrics > telegram-metrics.txt
curl -s http://localhost:8002/metrics > detector-metrics.txt

# 3. Kafka messages
docker exec ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic ddos-alerts \
  --from-beginning \
  --max-messages 10 > kafka-alerts.txt
```
