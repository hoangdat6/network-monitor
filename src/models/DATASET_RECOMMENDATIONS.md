# 📊 Dataset Recommendations cho DDoS Detection

## 🚨 Vấn đề với CICIDS2017

### Hạn chế:
1. **Không phân loại chi tiết** - Chỉ có label "DDoS" chung chung
2. **Dataset cũ (2017)** - Không phản ánh attack patterns hiện đại
3. **Thiếu attack vectors** - DNS amp, NTP amp, Memcached, Slowloris
4. **Không có encrypted traffic** - TLS 1.3, DoH, DoT
5. **Không có cloud patterns** - CDN, load balancers

## ✅ Datasets tốt hơn

### 1. **CIC-DDoS2019** ⭐ KHUYẾN NGHỊ
- **Link**: https://www.unb.ca/cic/datasets/ddos-2019.html
- **Ưu điểm**:
  - 12 loại DDoS attacks chi tiết
  - Modern attack vectors
  - 50M+ flows
- **DDoS Types**:
  - ✅ DNS Amplification
  - ✅ NTP Amplification  
  - ✅ NetBIOS Amplification
  - ✅ LDAP Amplification
  - ✅ MSSQL Amplification
  - ✅ UDP Flood
  - ✅ SYN Flood
  - ✅ TFTP Amplification
  - ✅ UDPLag
  - ✅ Portmap Amplification
  - ✅ SNMP Amplification
  - ✅ SSDP Amplification

### 2. **CIC-IoTDataset2022**
- **Link**: https://www.unb.ca/cic/datasets/iotdataset-2022.html
- **Ưu điểm**:
  - IoT botnet attacks
  - Mirai variants
  - Modern IoT DDoS patterns
- **Attack Types**:
  - ✅ Mirai botnet
  - ✅ BASHLITE botnet
  - ✅ Torii botnet

### 3. **UNSW-NB15**
- **Link**: https://research.unsw.edu.au/projects/unsw-nb15-dataset
- **Ưu điểm**:
  - Modern traffic patterns
  - Multiple attack categories
  - Real-world background traffic

### 4. **Custom Dataset Generation** 🎯
Tạo dataset riêng với tools:

#### **A. Sử dụng các tool tấn công**
```bash
# SYN Flood
hping3 -S -p 80 --flood <target>

# UDP Flood  
sudo ./udpflood.py <target> <port> <packet_size> <rate>

# HTTP Flood
ab -n 1000000 -c 1000 http://<target>/

# Slowloris
slowloris.py -s 500 <target>

# DNS Amplification
dnschef --fakeip <target> --file dns_records.txt
```

#### **B. Capture với CICFlowMeter**
```bash
# Capture benign traffic
cicflowmeter -i eth0 -c benign.csv

# Capture during attack
cicflowmeter -i eth0 -c attack_syn.csv
```

## 🎯 Khuyến nghị triển khai

### **Giai đoạn 1: Retrain với CIC-DDoS2019**
```python
# Download dataset
wget https://www.unb.ca/cic/datasets/ddos-2019.html

# Train multi-class model
LABELS = [
    'BENIGN',
    'DNS_AMP', 'NTP_AMP', 'LDAP_AMP',
    'UDP_FLOOD', 'SYN_FLOOD',
    'HTTP_FLOOD', 'SLOWLORIS'
]

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=20,
    class_weight='balanced'  # Handle imbalance
)
```

### **Giai đoạn 2: Hybrid Approach**
Kết hợp ML + Rule-based:

```python
def detect_ddos(flow):
    # Step 1: ML model predict
    ml_prediction = model.predict(flow)
    ml_confidence = model.predict_proba(flow).max()
    
    # Step 2: Rule-based verification
    if ml_prediction == 'SYN_FLOOD':
        if flow['SYN Flag Count'] < 5:
            return 'BENIGN', 'rule_override'
    
    # Step 3: Statistical anomaly detection
    if is_statistical_anomaly(flow):
        return 'UNKNOWN_ATTACK', 'anomaly'
    
    return ml_prediction, ml_confidence
```

### **Giai đoạn 3: Online Learning**
Update model với traffic thực tế:

```python
from river import ensemble, tree

# Incremental learning model
model = ensemble.AdaptiveRandomForestClassifier(
    n_models=10,
    max_depth=20
)

# Update continuously
for flow in stream:
    prediction = model.predict_one(flow)
    # Get feedback from security team
    if has_label(flow):
        model.learn_one(flow, flow['label'])
```

## 📈 So sánh khả năng phát hiện

| Attack Type | CICIDS2017 | CIC-DDoS2019 | Custom Dataset |
|------------|------------|--------------|----------------|
| SYN Flood | ✅ | ✅ | ✅ |
| UDP Flood | ✅ | ✅ | ✅ |
| HTTP Flood | ⚠️ Limited | ✅ | ✅ |
| DNS Amp | ❌ | ✅ | ✅ |
| NTP Amp | ❌ | ✅ | ✅ |
| Slowloris | ❌ | ❌ | ✅ |
| Memcached | ❌ | ❌ | ✅ |
| IoT Botnet | ❌ | ❌ | ⚠️ |

## 🔧 Migration Plan

### **Bước 1: Download CIC-DDoS2019**
```bash
cd /root/network_monitor/v2/src/data
wget https://...  # Download từ CIC
unzip ddos2019.zip
```

### **Bước 2: Update training script**
```bash
cd /root/network_monitor/v2/src/models
cp ddos_time_split_pipeline.py ddos_multiclass_pipeline.py
# Edit to support multi-class
```

### **Bước 3: Retrain model**
```bash
python ddos_multiclass_pipeline.py \
  --dataset data/ddos2019.csv \
  --labels DNS_AMP,NTP_AMP,SYN_FLOOD,UDP_FLOOD,HTTP_FLOOD \
  --output ddos_detector_v2
```

### **Bước 4: Update detector**
```python
# In detection/ddos-detector/detector.py
ATTACK_TYPES = {
    0: 'BENIGN',
    1: 'SYN_FLOOD',
    2: 'UDP_FLOOD',
    3: 'HTTP_FLOOD',
    4: 'DNS_AMP',
    5: 'NTP_AMP',
    6: 'LDAP_AMP',
    7: 'UNKNOWN_DDOS'
}
```

## 🎓 Tài liệu tham khảo

1. **CIC Datasets**: https://www.unb.ca/cic/datasets/
2. **DDoS Attack Taxonomy**: https://www.cloudflare.com/learning/ddos/
3. **ML for Network Security**: https://github.com/jmhIcoding/awesome-ml-cybersecurity
