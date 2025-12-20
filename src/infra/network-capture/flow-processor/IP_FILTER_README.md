# IP Filtering Configuration Guide

## 📋 Tổng quan

Flow Processor giờ đây hỗ trợ **dynamic IP filtering** thông qua file config YAML. Bạn có thể thay đổi danh sách IPs cần filter mà **không cần sửa code**, chỉ cần **restart container**.

## 🎯 Mục đích

Loại bỏ các IPs không cần thiết khỏi detection để:
- ✅ Giảm false positives
- ✅ Giảm noise từ legitimate traffic (DNS, CDN, etc.)
- ✅ Tập trung vào potential threats
- ✅ Tiết kiệm resources

## 📁 File cấu hình

**Location:** `src/infra/network-capture/flow-processor/ip_filter_config.yaml`

### Cấu trúc

```yaml
# Bật/tắt filtering
enabled: true

# Private/Local IPs - luôn được filter
local_ip_ranges:
  - "192.168."
  - "10."
  - "127."
  # ...

# Trusted IPs - DNS servers, specific IPs
trusted_ips:
  - "8.8.8.8"      # Google DNS
  - "1.1.1.1"      # Cloudflare DNS
  # ...

# Trusted IP prefixes - CDN, cloud services
trusted_ip_prefixes:
  - "74.125."      # Google
  - "104.16."      # Cloudflare
  # ...
```

## 🚀 Cách sử dụng

### Option 1: Sử dụng file mặc định

File config mặc định: `ip_filter_config.yaml` trong cùng thư mục với `processor.py`

```bash
# 1. Chỉnh sửa file config
nano src/infra/network-capture/flow-processor/ip_filter_config.yaml

# 2. Restart container
docker restart ids_flow_processor

# 3. Kiểm tra logs
docker logs ids_flow_processor | grep "IP Filter Config"
```

### Option 2: Sử dụng custom config path

Bạn có thể mount custom config file từ bên ngoài:

```yaml
# docker-compose.yml
services:
  flow-processor:
    environment:
      - IP_FILTER_CONFIG_PATH=/config/my_custom_filter.yaml
    volumes:
      - ./my_custom_filter.yaml:/config/my_custom_filter.yaml:ro
```

## 📝 Ví dụ cấu hình

### Ví dụ 1: Filter tất cả Google traffic

```yaml
enabled: true

local_ip_ranges:
  - "192.168."
  - "10."

trusted_ips:
  - "8.8.8.8"
  - "8.8.4.4"

trusted_ip_prefixes:
  - "74.125."      # Google
  - "142.250."     # Google
  - "142.251."     # Google
  - "172.217."     # Google
  - "172.253."     # Google
  - "216.58."      # Google
  - "64.233."      # Google
```

**Kết quả:** Tất cả traffic từ Google services sẽ bị loại bỏ

### Ví dụ 2: Chỉ filter local IPs

```yaml
enabled: true

local_ip_ranges:
  - "192.168."
  - "10."
  - "127."

trusted_ips: []
trusted_ip_prefixes: []
```

**Kết quả:** Chỉ filter private IPs, giữ lại tất cả external traffic

### Ví dụ 3: Filter cả AWS và Azure

```yaml
enabled: true

local_ip_ranges:
  - "192.168."
  - "10."

trusted_ips: []

trusted_ip_prefixes:
  # AWS
  - "52."
  - "54."
  # Azure
  - "13."
  - "40."
```

**Kết quả:** Traffic từ AWS và Azure sẽ bị loại bỏ

### Ví dụ 4: Tắt filtering hoàn toàn

```yaml
enabled: false
```

**Kết quả:** Tất cả traffic đều được giữ lại (không filter gì cả)

## 🔍 Kiểm tra cấu hình

### Xem logs khi khởi động

```bash
docker logs ids_flow_processor | grep -A 5 "IP Filter Config"
```

**Output mẫu:**
```
IP Filter Config:
  - Enabled: True
  - Local IP ranges: 19 ranges
  - Trusted IPs: 8 IPs
  - Trusted prefixes: 10 prefixes
```

### Test filtering

```bash
# Xem số lượng flows được filter
docker logs ids_flow_processor | grep "Filtered"

# Output mẫu:
# Filtered 1234 flows (local/trusted IPs), kept 567 external flows
```

## 🛠️ Troubleshooting

### Vấn đề 1: Config không được load

**Triệu chứng:** Logs vẫn hiển thị "using defaults"

**Giải pháp:**
```bash
# Kiểm tra file tồn tại
docker exec ids_flow_processor ls -la /app/ip_filter_config.yaml

# Kiểm tra permissions
docker exec ids_flow_processor cat /app/ip_filter_config.yaml
```

### Vấn đề 2: YAML syntax error

**Triệu chứng:** Logs hiển thị "Failed to load IP filter config"

**Giải pháp:**
```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('ip_filter_config.yaml'))"

# Hoặc dùng online validator
# https://www.yamllint.com/
```

### Vấn đề 3: Vẫn thấy Google IPs trong alerts

**Nguyên nhân:** Config chưa được apply hoặc container chưa restart

**Giải pháp:**
```bash
# 1. Verify config
cat src/infra/network-capture/flow-processor/ip_filter_config.yaml

# 2. Restart container
docker restart ids_flow_processor

# 3. Wait 10 seconds
sleep 10

# 4. Check logs
docker logs ids_flow_processor --tail 50
```

## 📊 Best Practices

### 1. Bắt đầu conservative

```yaml
# Chỉ filter những gì chắc chắn
trusted_ips:
  - "8.8.8.8"      # Google DNS
  - "8.8.4.4"

trusted_ip_prefixes:
  - "74.125."      # Google services
```

### 2. Monitor và adjust

```bash
# Xem top source IPs trong alerts
docker exec ids_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic ddos-alerts \
  --from-beginning \
  --max-messages 100 | \
  jq -r '.attacker_ips[]' | \
  sort | uniq -c | sort -rn | head -20
```

### 3. Document changes

Thêm comments trong config file:

```yaml
trusted_ips:
  - "8.8.8.8"      # Added 2025-12-20: Too many DNS queries
  - "1.1.1.1"      # Added 2025-12-20: Cloudflare DNS
```

### 4. Backup config

```bash
# Backup trước khi thay đổi
cp ip_filter_config.yaml ip_filter_config.yaml.backup.$(date +%Y%m%d)
```

## 🔄 Workflow thông thường

```bash
# 1. Phân tích alerts hiện tại
./check_alerts.sh

# 2. Xác định IPs cần filter
docker logs ids_rule_detector | grep "ALERT" | grep -oP '\d+\.\d+\.\d+\.\d+' | sort | uniq -c | sort -rn

# 3. Thêm vào config
nano src/infra/network-capture/flow-processor/ip_filter_config.yaml

# 4. Restart
docker restart ids_flow_processor

# 5. Verify
docker logs ids_flow_processor | grep "IP Filter Config"

# 6. Monitor trong 10-15 phút
watch -n 30 './check_alerts.sh'
```

## 📈 Monitoring

### Metrics quan trọng

```bash
# 1. Số flows được filter
docker logs ids_flow_processor | grep "Filtered" | tail -10

# 2. Số flows được giữ lại
docker logs ids_flow_processor | grep "kept" | tail -10

# 3. Alert rate trước và sau filtering
curl -s http://localhost:8002/metrics | grep rule_detector_alerts_total
```

## 💡 Tips

1. **Không filter quá nhiều:** Có thể bỏ lỡ real attacks từ compromised cloud servers

2. **Review định kỳ:** Mỗi tuần review lại config để adjust

3. **Test trước khi apply:** Test với một vài flows trước khi apply cho production

4. **Keep it simple:** Bắt đầu với ít rules, thêm dần theo nhu cầu

## 🆘 Support

Nếu cần help, cung cấp:

```bash
# 1. Current config
cat src/infra/network-capture/flow-processor/ip_filter_config.yaml

# 2. Logs
docker logs ids_flow_processor --tail 100

# 3. Sample flows
head -20 flows.csv
```

---

**Last updated:** 2025-12-20  
**Version:** 1.0
