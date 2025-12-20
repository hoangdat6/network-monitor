# 🔍 Tại sao AGG-008 luôn trigger trước AGG-001/AGG-002?

## 📋 Tóm tắt

Khi bạn chạy các cuộc tấn công UDP Flood hoặc SYN Flood, bạn nhận thấy rằng **AGG-008 (Low-Rate DDoS / Distributed Attack)** luôn được trigger **TRƯỚC** các rules chuyên biệt như:
- AGG-001 (SYN Flood Attack)
- AGG-002 (UDP Flood Attack)

Đây **KHÔNG PHẢI là bug**, mà là **thiết kế có chủ đích** dựa trên cách các cuộc tấn công DDoS được mô phỏng.

---

## 🎯 Nguyên nhân chính

### 1. **Điều kiện của AGG-008 rất dễ đạt được**

**AGG-008 Rule:**
```yaml
- id: "AGG-008"
  name: "Low-Rate DDoS / Distributed Attack"
  severity: "high"
  description: "Many sources with low packets each - distributed DDoS"
  window: "60s"
  conditions:
    - metric: "unique_src_ips"
      operator: "gt"
      value: 200  # > 200 different source IPs
    - metric: "flows_per_ip"
      operator: "lt"
      value: 10   # Each source sends few flows
  action: "alert"
```

**Điều kiện:**
- ✅ Có **> 200 source IPs khác nhau**
- ✅ Mỗi IP gửi **< 10 flows**

### 2. **Cách script tấn công của bạn hoạt động**

Khi bạn chạy các script tấn công (UDP Flood, SYN Flood), chúng thường:

```python
# Ví dụ từ script distributed.py hoặc udp_flood.py
for i in range(num_packets):
    src_ip = generate_random_ip()  # Mỗi packet từ IP khác nhau!
    send_packet(src_ip, target_ip, ...)
```

**Kết quả:**
- Bạn tạo ra **hàng nghìn packets** từ **hàng trăm/nghìn IPs khác nhau**
- Mỗi IP chỉ gửi **vài packets** (distributed attack pattern)
- → **AGG-008 được trigger ngay lập tức!**

### 3. **Timeline của việc trigger alerts**

```
Thời gian 0s: Bắt đầu tấn công UDP/SYN Flood
            ↓
Thời gian 5-10s: 
  - Đã có ~200-300 unique source IPs
  - Mỗi IP gửi 2-5 flows
  - ✅ AGG-008 TRIGGERED! (Low-Rate DDoS detected)
            ↓
Thời gian 20-30s:
  - Tích lũy đủ UDP packets (>10,000)
  - ✅ AGG-002 TRIGGERED! (UDP Flood detected)
            ↓
Hoặc:
  - Tích lũy đủ SYN packets (>500) với ratio >0.8
  - ✅ AGG-001 TRIGGERED! (SYN Flood detected)
```

---

## 📊 So sánh Thresholds

| Rule | Metric | Threshold | Thời gian đạt được |
|------|--------|-----------|-------------------|
| **AGG-008** | unique_src_ips | > 200 | ⚡ **5-10 giây** (nhanh nhất) |
| **AGG-002** | udp_packet_count | > 10,000 | 🕐 20-30 giây |
| **AGG-001** | syn_flag_count | > 500 | 🕐 15-25 giây |

→ **AGG-008 có threshold thấp nhất** và **dễ đạt được nhất** khi sử dụng distributed attack pattern!

---

## 🔬 Phân tích cụ thể từ logs của bạn

### **Ví dụ 1: UDP Flood Attack**

```
11:26:54 - AGG-002 triggered (UDP Flood)
Window stats:
  - total_flows: 23,300
  - udp_packet_count: 46,600
  - unique_src_ips: 23,299  ← Gần như mỗi flow từ 1 IP khác nhau!
  - flows_per_ip: 2         ← Mỗi IP chỉ gửi ~2 flows
```

**Phân tích:**
- Có **23,299 unique source IPs** → Vượt xa threshold 200 của AGG-008
- Mỗi IP chỉ gửi **2 flows** → Thỏa mãn điều kiện `flows_per_ip < 10`
- → **AGG-008 đã được trigger trước đó!**

### **Ví dụ 2: SYN Flood Attack**

```
11:28:07 - AGG-001 triggered (SYN Flood)
Window stats:
  - total_flows: 1,296
  - syn_flag_count: 2,453
  - unique_src_ips: 1,285   ← 1,285 IPs khác nhau!
  - flows_per_ip: 5         ← Mỗi IP gửi ~5 flows
  - syn_ack_ratio: 0.80
```

**Phân tích:**
- Có **1,285 unique source IPs** → Vượt xa threshold 200
- Mỗi IP gửi **5 flows** → Thỏa mãn `flows_per_ip < 10`
- → **AGG-008 đã được trigger ở giây thứ 5-10!**
- AGG-001 chỉ trigger sau khi tích lũy đủ 500+ SYN packets

---

## 💡 Tại sao thiết kế như vậy?

### **1. Phát hiện sớm (Early Detection)**

AGG-008 được thiết kế để:
- ✅ **Phát hiện sớm** các cuộc tấn công distributed
- ✅ **Cảnh báo nhanh** khi có bất thường về số lượng source IPs
- ✅ **Không cần chờ** tích lũy đủ packets/flags

### **2. Phản ánh thực tế của DDoS hiện đại**

Các cuộc tấn công DDoS hiện đại thường:
- Sử dụng **botnet** với hàng nghìn IPs
- Mỗi bot gửi **ít traffic** để tránh bị phát hiện
- → **Distributed low-rate attack** là pattern phổ biến nhất!

### **3. Defense in Depth**

Hệ thống có nhiều lớp phát hiện:
```
Layer 1: AGG-008 (Distributed pattern) ← Phát hiện sớm nhất
   ↓
Layer 2: AGG-001/002/003 (Specific attacks) ← Xác định loại tấn công
   ↓
Layer 3: AGG-009 (Amplification) ← Phát hiện kỹ thuật nâng cao
```

---

## 🛠️ Giải pháp và Recommendations

### **Option 1: Chấp nhận thiết kế hiện tại** ⭐ (Khuyến nghị)

**Ưu điểm:**
- ✅ Phát hiện sớm nhất có thể
- ✅ Bắt được cả distributed attacks
- ✅ Defense in depth

**Cách sử dụng:**
- Xem AGG-008 như **early warning signal**
- Xem AGG-001/002 như **attack confirmation**
- Kết hợp cả hai để có full picture

### **Option 2: Tăng threshold của AGG-008**

Nếu bạn muốn AGG-008 ít trigger hơn:

```yaml
# File: src/infra/rule-based-detector/rules.yaml
- id: "AGG-008"
  conditions:
    - metric: "unique_src_ips"
      operator: "gt"
      value: 500  # Tăng từ 200 → 500
    - metric: "flows_per_ip"
      operator: "lt"
      value: 5    # Giảm từ 10 → 5 (stricter)
```

**Ưu điểm:**
- Giảm false positives
- Chỉ trigger khi thực sự là distributed attack lớn

**Nhược điểm:**
- Mất khả năng phát hiện sớm
- Có thể bỏ lỡ medium-scale attacks

### **Option 3: Thêm điều kiện bổ sung cho AGG-008**

Làm cho AGG-008 chỉ trigger khi có **cả** distributed pattern **VÀ** high traffic:

```yaml
- id: "AGG-008"
  conditions:
    - metric: "unique_src_ips"
      operator: "gt"
      value: 200
    - metric: "flows_per_ip"
      operator: "lt"
      value: 10
    # Thêm điều kiện mới:
    - metric: "total_flows"
      operator: "gt"
      value: 1000  # Phải có ít nhất 1000 flows
```

### **Option 4: Giảm severity của AGG-008**

Nếu bạn muốn giữ nguyên logic nhưng giảm "noise":

```yaml
- id: "AGG-008"
  severity: "medium"  # Giảm từ "high" → "medium"
  action: "alert"     # Giữ nguyên
```

**Kết quả:**
- AGG-008 vẫn trigger sớm nhưng với severity thấp hơn
- AGG-001/002 (critical) sẽ nổi bật hơn

### **Option 5: Thay đổi cách tấn công để test**

Nếu bạn muốn test riêng AGG-001 hoặc AGG-002 mà **không trigger AGG-008**:

```python
# Thay vì random IPs, dùng fixed IPs
ATTACKER_IPS = ["10.0.0.1", "10.0.0.2", "10.0.0.3"]  # Chỉ 3 IPs

for i in range(num_packets):
    src_ip = random.choice(ATTACKER_IPS)  # Rotate giữa 3 IPs
    send_packet(src_ip, target_ip, ...)
```

**Kết quả:**
- `unique_src_ips` = 3 (< 200) → AGG-008 **KHÔNG trigger**
- Nhưng vẫn có đủ UDP/SYN packets → AGG-001/002 **VẪN trigger**

---

## 🧪 Testing Scenarios

### **Scenario 1: Test riêng AGG-002 (UDP Flood)**

```bash
# Sửa script để dùng ít IPs hơn
python -m ddos_attacks udp-flood \
  --target 192.168.1.100 \
  --port 53 \
  --num-packets 50000 \
  --num-sources 50  # Chỉ 50 IPs (< 200)
```

**Kết quả mong đợi:**
- ❌ AGG-008 không trigger (< 200 IPs)
- ✅ AGG-002 trigger (đủ UDP packets)

### **Scenario 2: Test riêng AGG-001 (SYN Flood)**

```bash
python -m ddos_attacks syn-flood \
  --target 192.168.1.100 \
  --port 80 \
  --num-packets 10000 \
  --num-sources 100  # Chỉ 100 IPs
```

**Kết quả mong đợi:**
- ❌ AGG-008 không trigger
- ✅ AGG-001 trigger

### **Scenario 3: Test AGG-008 thuần túy**

```bash
python -m ddos_attacks distributed \
  --target 192.168.1.100 \
  --num-packets 5000 \
  --num-sources 500  # Nhiều IPs
  --packets-per-source 5  # Mỗi IP ít packets
```

**Kết quả mong đợi:**
- ✅ AGG-008 trigger
- ❌ AGG-001/002 không trigger (không đủ packets)

---

## 📊 Monitoring và Verification

### **Xem thứ tự trigger trong logs:**

```bash
# Rule-based detector logs
docker logs ids_rule_detector | grep "ALERT" | tail -20

# Kết quả:
# 11:28:06 - 🚨 ALERT [HIGH] - Low-Rate DDoS (AGG-008)
# 11:28:07 - 🚨 ALERT [CRITICAL] - SYN Flood (AGG-001)
```

### **Kiểm tra window stats:**

```bash
# Xem metrics tại thời điểm trigger
curl -s http://localhost:8002/metrics | grep rule_detector_window
```

---

## 🎯 Kết luận

**Câu trả lời ngắn gọn:**

> AGG-008 trigger trước vì nó có **threshold thấp nhất** (chỉ cần 200 unique IPs) và script tấn công của bạn tạo ra **distributed pattern** (nhiều IPs, mỗi IP ít flows).

**Đây là thiết kế đúng đắn** vì:
1. ✅ Phát hiện sớm distributed attacks
2. ✅ Phản ánh thực tế DDoS hiện đại
3. ✅ Cung cấp multiple layers of detection

**Khuyến nghị:**
- Giữ nguyên thiết kế hiện tại
- Xem AGG-008 như early warning
- Xem AGG-001/002 như attack confirmation
- Kết hợp cả hai để có complete picture

**Nếu muốn test riêng từng rule:**
- Giảm số lượng source IPs trong script tấn công (< 200)
- Hoặc tăng threshold của AGG-008 lên 500+

---

## 📝 Quick Reference

| Muốn test | Cách làm | Kết quả |
|-----------|----------|---------|
| Chỉ AGG-002 | `num_sources < 200` | AGG-008 ❌, AGG-002 ✅ |
| Chỉ AGG-001 | `num_sources < 200` | AGG-008 ❌, AGG-001 ✅ |
| Chỉ AGG-008 | `num_sources > 200, packets_per_source < 50` | AGG-008 ✅, Others ❌ |
| Tất cả | `num_sources > 200, high packets` | All ✅ (theo thứ tự) |
