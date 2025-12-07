# Telegram Notifier Configuration

## Setup Instructions

### 1. Tạo Telegram Bot

1. Mở Telegram và tìm **@BotFather**
2. Gửi command `/newbot`
3. Đặt tên cho bot (ví dụ: "DDoS Alert Bot")
4. Đặt username cho bot (phải kết thúc bằng "bot", ví dụ: "ddos_alert_bot")
5. BotFather sẽ trả về **BOT TOKEN** - save lại token này

### 2. Lấy Chat ID

Có 2 cách:

**Cách 1: Gửi message trực tiếp cho bot**
1. Tìm bot vừa tạo trong Telegram
2. Gửi message `/start`
3. Truy cập URL: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Tìm `"chat":{"id":123456789}` trong response - đó là Chat ID của bạn

**Cách 2: Tạo group chat**
1. Tạo group chat mới trong Telegram
2. Thêm bot vào group
3. Gửi một message bất kỳ trong group
4. Truy cập URL: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Tìm `"chat":{"id":-123456789}` - Chat ID của group sẽ là số âm

### 3. Cấu hình Environment Variables

Tạo file `.env` trong thư mục `v2/src/` hoặc set environment variables:

```bash
# Telegram Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Kafka Configuration (optional - defaults shown)
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_ALERT_TOPIC=ddos-alerts

# Metrics port (optional)
METRICS_PORT=8000
```

### 4. Test Bot

```bash
# Test xem bot có hoạt động không
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"

# Gửi test message
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "<YOUR_CHAT_ID>", "text": "Test message"}'
```

### 5. Chạy Service

```bash
cd v2/src
docker-compose -f docker-compose.monitoring.yml up -d telegram-notifier
```

### 6. Kiểm tra logs

```bash
docker logs -f telegram-notifier
```

## Format thông báo

Bot sẽ gửi thông báo với format sau:

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

## Severity Levels

- ⚠️ **LOW**: Minor suspicious activity
- 🟡 **MEDIUM**: Moderate threat detected
- 🔴 **HIGH**: Significant attack detected
- 🚨 **CRITICAL**: Severe attack requiring immediate action

## Troubleshooting

### Bot không gửi được message

1. Kiểm tra BOT_TOKEN đúng chưa:
   ```bash
   docker exec telegram-notifier env | grep TELEGRAM_BOT_TOKEN
   ```

2. Kiểm tra Chat ID đúng chưa:
   ```bash
   docker exec telegram-notifier env | grep TELEGRAM_CHAT_ID
   ```

3. Kiểm tra bot có quyền gửi message không (nếu dùng group chat)

### Không nhận được alerts

1. Kiểm tra Kafka connection:
   ```bash
   docker logs telegram-notifier | grep -i kafka
   ```

2. Kiểm tra xem có alerts được gửi vào topic không:
   ```bash
   docker exec -it kafka kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 \
     --topic ddos-alerts \
     --from-beginning
   ```

3. Xem Prometheus metrics:
   ```bash
   curl http://localhost:8000/metrics
   ```

## Metrics

Service expose các metrics sau tại port 8000:

- `telegram_alerts_received_total`: Tổng số alerts nhận được
- `telegram_alerts_sent_total`: Tổng số alerts gửi thành công
- `telegram_alerts_failed_total`: Tổng số alerts gửi thất bại
- `telegram_notification_seconds`: Thời gian gửi notification

## Security Notes

- **Không commit** BOT_TOKEN vào Git
- Sử dụng `.env` file hoặc Docker secrets
- Giới hạn chat ID (chỉ gửi cho users/groups được authorize)
- Xem xét rate limiting để tránh spam
