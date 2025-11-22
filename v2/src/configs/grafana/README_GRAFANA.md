# 📊 Grafana Dashboards - Network Monitor System

## Overview

Hệ thống monitoring với 3 dashboards chính:
1. **DDoS Detection & Network Monitoring** - Theo dõi DDoS attacks và network traffic
2. **Container & System Monitoring** - Giám sát containers và host system
3. **SmartShield Security Dashboard** - Tổng quan bảo mật (existing)

---

## 🚀 Quick Start

### 1. Start Grafana Service

```bash
cd v2/src
docker-compose -f docker-compose.monitoring.yml up -d grafana
```

### 2. Access Grafana

- **URL**: http://localhost:3000
- **Username**: `admin`
- **Password**: `admin`

Lần đầu login sẽ được yêu cầu đổi password (có thể skip).

### 3. View Dashboards

Dashboards tự động được load từ provisioning:
- Home → Dashboards → Browse
- Chọn dashboard muốn xem

---

## 📈 Dashboard Details

### 1. DDoS Detection & Network Monitoring

**File**: `ddos-detection-dashboard.json`

**Panels**:
- **Total DDoS Alerts** - Tổng số alerts phát hiện được
- **Total Flows Processed** - Số lượng network flows đã xử lý
- **Active Attacking IPs** - Số IP đang tấn công
- **Flows in Current Window** - Flows trong sliding window hiện tại
- **Flow Processing Rate** - Tốc độ xử lý flows (flows/sec)
- **Suspicious Flows by Attack Type** - Phân loại theo loại tấn công
- **ML Model Prediction Latency** - Độ trễ của ML model (P95, P99)
- **DDoS Alerts by Severity** - Alerts theo mức độ (low/medium/high/critical)
- **Network Traffic (Bytes/sec)** - Lưu lượng mạng (RX/TX)
- **Network Traffic (Packets/sec)** - Số packets (RX/TX)
- **Top 10 Containers by CPU Usage** - Containers tiêu tốn CPU nhiều nhất
- **Top 10 Containers by Memory Usage** - Containers tiêu tốn RAM nhiều nhất

**Metrics sử dụng**:
```promql
# DDoS Detection metrics (từ ddos-detector)
ddos_alerts_triggered_total
ddos_flows_processed_total
ddos_flows_suspicious_total
ddos_active_attackers
ddos_flows_in_window
ddos_prediction_seconds_bucket

# Node Exporter metrics (network)
node_network_receive_bytes_total
node_network_transmit_bytes_total
node_network_receive_packets_total
node_network_transmit_packets_total

# cAdvisor metrics
container_cpu_usage_seconds_total
container_memory_usage_bytes
```

**Use cases**:
- Real-time monitoring của DDoS attacks
- Phát hiện network anomalies
- Đánh giá performance của ML model
- Alert khi có attack patterns

---

### 2. Container & System Monitoring

**File**: `container-monitoring-dashboard.json`

**Panels**:
- **Container CPU Usage (%)** - CPU usage của từng container
- **Container Memory Usage** - RAM usage của từng container
- **Container Network I/O** - Network traffic per container
- **Container Disk I/O** - Disk read/write per container
- **Host System Resources** - CPU và Memory của host
- **Host Disk Usage** - Disk usage của host
- **Container Details** - Bảng tổng hợp thông tin containers

**Metrics sử dụng**:
```promql
# Container metrics (cAdvisor)
container_cpu_usage_seconds_total
container_memory_usage_bytes
container_network_receive_bytes_total
container_network_transmit_bytes_total
container_fs_reads_bytes_total
container_fs_writes_bytes_total

# Host metrics (Node Exporter)
node_memory_MemAvailable_bytes
node_memory_MemTotal_bytes
node_cpu_seconds_total
node_filesystem_avail_bytes
node_filesystem_size_bytes
```

**Use cases**:
- Monitoring resource usage của containers
- Phát hiện containers có vấn đề về performance
- Capacity planning
- Identify resource bottlenecks

---

### 3. SmartShield Security Dashboard (Existing)

**File**: `smartshield-dashboard.json`

Tổng quan về security metrics, ML model performance, attack types.

---

## 🔧 Configuration

### Datasource Configuration

**File**: `configs/grafana/provisioning/datasources/datasource.yaml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

### Dashboard Provisioning

**File**: `configs/grafana/provisioning/dashboards/dashboard.yaml`

```yaml
apiVersion: 1
providers:
  - name: 'SmartShield Dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

---

## 📊 Custom Metrics

### Adding Your Own Metrics

Để thêm metrics mới vào dashboard:

1. **Export metrics từ application**
```python
from prometheus_client import Counter, Gauge

custom_metric = Counter('my_custom_metric', 'Description')
custom_metric.inc()
```

2. **Configure Prometheus scrape target**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'my-app'
    static_configs:
      - targets: ['my-app:8000']
```

3. **Add panel to Grafana**
- Edit dashboard
- Add Panel
- Query: `rate(my_custom_metric[5m])`
- Save

---

## 🎨 Customization

### Modify Existing Dashboards

Có 2 cách:

**Option 1: Via UI** (recommended cho testing)
1. Login vào Grafana
2. Open dashboard
3. Click ⚙️ Settings → Make editable
4. Edit panels, add queries
5. Save

**Option 2: Edit JSON** (recommended cho version control)
1. Edit file `.json` trong `configs/grafana/dashboards/`
2. Restart Grafana hoặc đợi auto-reload (10s)

### Create New Dashboard

```bash
# Copy template
cp configs/grafana/dashboards/ddos-detection-dashboard.json \
   configs/grafana/dashboards/my-dashboard.json

# Edit JSON
# Change: title, uid, panels, queries

# Restart Grafana
docker restart grafana
```

---

## 🔍 Useful Queries

### DDoS Detection

```promql
# Alert rate (alerts per minute)
rate(ddos_alerts_triggered_total[1m]) * 60

# Suspicious flow percentage
(ddos_flows_suspicious_total / ddos_flows_processed_total) * 100

# Top attacking IPs (need labels)
topk(10, sum by (src_ip) (ddos_flows_suspicious_total))
```

### Network Traffic

```promql
# Total bandwidth (all interfaces)
sum(rate(node_network_receive_bytes_total[5m])) * 8  # bits/sec
sum(rate(node_network_transmit_bytes_total[5m])) * 8

# Network errors
rate(node_network_receive_errs_total[5m])
rate(node_network_transmit_errs_total[5m])
```

### Container Performance

```promql
# Container CPU %
rate(container_cpu_usage_seconds_total{name="ids_ddos_detector"}[5m]) * 100

# Container Memory %
(container_memory_usage_bytes / container_spec_memory_limit_bytes) * 100

# Container restart count
changes(container_start_time_seconds{name=~".+"}[1h])
```

---

## 🚨 Alerting

### Configure Alert Rules

Grafana có thể tạo alerts từ panels:

1. Edit panel → Alert tab
2. Set conditions (e.g., "when query > threshold")
3. Configure notification channel (Email, Slack, Telegram)

**Example Alert**:
```
Alert: High DDoS Alert Rate
Condition: rate(ddos_alerts_triggered_total[5m]) > 10
For: 2 minutes
Notification: Send to Telegram
```

---

## 📱 Access from External

Để access Grafana từ bên ngoài server:

### Option 1: Port Forward (Development)
```bash
ssh -L 3000:localhost:3000 user@server
# Access: http://localhost:3000
```

### Option 2: Nginx Reverse Proxy (Production)
```nginx
server {
    listen 80;
    server_name grafana.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option 3: Change bind address (⚠️ Security risk)
```yaml
# docker-compose.monitoring.yml
grafana:
  ports:
    - "0.0.0.0:3000:3000"  # Listen on all interfaces
```

---

## 🛠️ Troubleshooting

### Dashboard không hiển thị data

**Kiểm tra**:
```bash
# 1. Prometheus đang chạy?
docker ps | grep prometheus
curl http://localhost:9090/-/healthy

# 2. Targets đang scrape?
curl http://localhost:9090/api/v1/targets

# 3. Metrics có data?
curl http://localhost:9090/api/v1/query?query=ddos_flows_processed_total

# 4. Grafana datasource OK?
# Login Grafana → Configuration → Data Sources → Test
```

### Dashboard không auto-load

```bash
# Check provisioning config
docker exec grafana cat /etc/grafana/provisioning/dashboards/dashboard.yaml

# Check dashboard files
docker exec grafana ls -la /var/lib/grafana/dashboards/

# Restart Grafana
docker restart grafana
```

### Permission denied

```bash
# Fix volume permissions
sudo chown -R 472:472 /var/lib/docker/volumes/grafana_data

# Or use root user (not recommended)
# docker-compose.monitoring.yml
# environment:
#   - GF_SECURITY_ADMIN_USER=admin
```

---

## 📚 Resources

- **Grafana Documentation**: https://grafana.com/docs/
- **Prometheus Query Examples**: https://prometheus.io/docs/prometheus/latest/querying/examples/
- **Pre-built Dashboards**: https://grafana.com/grafana/dashboards/
- **Alert Notification Channels**: https://grafana.com/docs/grafana/latest/alerting/notifications/

---

## 🎯 Next Steps

1. **Thêm alerting rules** cho critical metrics
2. **Tích hợp Telegram notifications** cho alerts
3. **Tạo dashboard cho Nginx metrics** (cần nginx-prometheus-exporter)
4. **Setup Grafana authentication** (LDAP, OAuth) nếu deploy production
5. **Backup dashboards** định kỳ (export JSON)

---

**Last Updated**: 2025-11-22  
**Grafana Version**: latest (compatible with 8.x+)  
**Dashboards**: 3 (DDoS Detection, Container Monitoring, Security Overview)
