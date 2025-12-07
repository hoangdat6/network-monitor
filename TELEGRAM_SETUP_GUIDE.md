# Telegram Notifier Setup Guide

## ✅ Setup đã hoàn tất!

Tôi đã tạo hệ thống gửi thông báo Telegram cho DDoS alerts với các thành phần sau:

### 📁 Files đã tạo:

```
v2/src/
├── response/telegram-notifier/
│   ├── telegram_notifier.py      # Main service code
│   ├── Dockerfile                # Docker image
│   ├── requirements.txt          # Python dependencies
│   └── README.md                 # Chi tiết hướng dẫn
├── .env.telegram.example         # Template cho env vars
└── scripts/
    ├── setup_telegram.sh         # Script setup và test bot
    └── test_telegram_alert.sh    # Script gửi test alert
```

### 🚀 Hướng dẫn sử dụng nhanh:

#### Bước 1: Tạo Telegram Bot

1. Mở Telegram và tìm **@BotFather**
2. Gửi command: `/newbot`
3. Đặt tên bot: `DDoS Alert Bot` (hoặc tên khác)
4. Đặt username: `ddos_alert_bot` (phải kết thúc bằng "bot")
5. **Lưu lại BOT_TOKEN** mà BotFather gửi cho bạn

#### Bước 2: Lấy Chat ID

**Option A - Cá nhân (Personal chat):**
1. Tìm bot vừa tạo trong Telegram
2. Gửi message: `/start`
3. Mở trình duyệt, truy cập:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Tìm `"chat":{"id":123456789}` - đó là Chat ID của bạn

**Option B - Group chat:**
1. Tạo group mới trong Telegram
2. Thêm bot vào group
3. Gửi 1 message bất kỳ trong group
4. Truy cập URL như trên
5. Chat ID của group sẽ là số âm: `-123456789`

#### Bước 3: Cấu hình Environment

```bash
cd /root/network_monitor/v2/src

# Copy template
cp .env.telegram.example .env

# Edit file .env và thay thế:
# - TELEGRAM_BOT_TOKEN=your_bot_token_here  → token thật
# - TELEGRAM_CHAT_ID=your_chat_id_here      → chat_id thật
nano .env
```

#### Bước 4: Test Setup

```bash
# Chạy script setup - nó sẽ test bot connection và gửi test message
./scripts/setup_telegram.sh
```

Bạn sẽ nhận được message test trong Telegram nếu setup đúng!

#### Bước 5: Start Service

```bash
# Build và chạy telegram-notifier
docker-compose -f docker-compose.monitoring.yml up -d telegram-notifier

# Kiểm tra logs
docker logs -f telegram-notifier

# Kiểm tra health
docker ps | grep telegram-notifier
```

#### Bước 6: Test Alert

```bash
# Gửi một fake alert để test
./scripts/test_telegram_alert.sh
```

Bạn sẽ nhận được thông báo DDoS alert trong Telegram!

---

## 📊 Monitoring

### View Metrics
```bash
curl http://localhost:8005/metrics
```

Metrics available:
- `telegram_alerts_received_total` - Alerts nhận được
- `telegram_alerts_sent_total` - Alerts gửi thành công
- `telegram_alerts_failed_total` - Alerts gửi thất bại
- `telegram_notification_seconds` - Thời gian gửi

### View Logs
```bash
# Real-time logs
docker logs -f telegram-notifier

# Last 100 lines
docker logs --tail 100 telegram-notifier
```

---

## 🎯 Cách hoạt động

1. **DDoS Detector** phát hiện tấn công → gửi alert vào Kafka topic `ddos-alerts`
2. **Telegram Notifier** subscribe topic → nhận alerts
3. Format thành message đẹp với emoji, metrics, recommendations
4. Gửi qua Telegram Bot API → bạn nhận được thông báo ngay lập tức!

---

## 📱 Format thông báo

Thông báo sẽ có dạng:

```
🚨 DDoS ALERT - CRITICAL

Thời gian: 2025-12-07 10:30:45
Loại tấn công: DDoS
Target IP: 192.168.1.100
Số flows: 1500
Confidence: 95.50%
Time window: 60s

🎯 Attacker IPs (3):
  • 10.0.0.5
  • 10.0.0.8
  • 10.0.0.12

📊 Metrics:
  • flows_per_second: 25.00
  • unique_sources: 3

💡 Khuyến nghị:
Consider blocking source IPs and rate limiting

Alert ID: ddos-1733567445-abc123
```

**Severity Levels:**
- ⚠️ LOW - Minor suspicious activity
- 🟡 MEDIUM - Moderate threat
- 🔴 HIGH - Significant attack
- 🚨 CRITICAL - Severe attack

---

## 🔧 Troubleshooting

### Bot không gửi được message?

```bash
# 1. Check env vars
docker exec telegram-notifier env | grep TELEGRAM

# 2. Test bot manually
curl "https://api.telegram.org/bot<TOKEN>/getMe"

# 3. Test send message
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>" \
  -d "text=Test"
```

### Không nhận được alerts?

```bash
# 1. Check Kafka connection
docker logs telegram-notifier | grep -i kafka

# 2. Check if alerts are being sent to Kafka
docker exec -it kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic ddos-alerts \
  --from-beginning

# 3. Send test alert
./scripts/test_telegram_alert.sh
```

### Service không start?

```bash
# Check if .env is loaded
docker-compose -f docker-compose.monitoring.yml config | grep TELEGRAM

# Rebuild image
docker-compose -f docker-compose.monitoring.yml build telegram-notifier

# Start with logs
docker-compose -f docker-compose.monitoring.yml up telegram-notifier
```

---

## 🔐 Security Notes

⚠️ **QUAN TRỌNG:**
- **KHÔNG commit** BOT_TOKEN vào Git
- Thêm `.env` vào `.gitignore`
- Giới hạn ai có thể nhận notifications (chỉ authorized chat IDs)
- Xem xét rate limiting để tránh spam
- Rotate BOT_TOKEN định kỳ nếu bị leak

---

## 📖 Tài liệu chi tiết

Xem thêm tại: `/root/network_monitor/v2/src/response/telegram-notifier/README.md`

---

## 🎉 Done!

Service đã sẵn sàng! Bất cứ khi nào hệ thống phát hiện DDoS attack, bạn sẽ nhận được thông báo ngay lập tức trên Telegram. 🚀
