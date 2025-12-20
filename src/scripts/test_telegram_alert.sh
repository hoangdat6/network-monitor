#!/bin/bash

# Script để test gửi alert giả vào Kafka để kiểm tra Telegram notification

echo "=========================================="
echo "Test Telegram Notifier với Fake Alert"
echo "=========================================="
echo ""

# Check if kafka is running
if ! docker ps | grep -q ids_kafka; then
    echo "❌ Kafka container is not running"
    echo "Please start Kafka first: docker-compose -f docker-compose.network.yml up -d kafka zookeeper"
    exit 1
fi

# Tạo test alert
ALERT_ID="test-$(date +%s)"
TIMESTAMP=$(date -Iseconds)

TEST_ALERT='{"alert_id":"'${ALERT_ID}'","timestamp":"'${TIMESTAMP}'","severity":"HIGH","attack_type":"DDoS","attacker_ips":["10.0.0.5","10.0.0.8","10.0.0.12"],"target_ip":"192.168.1.100","flow_count":1500,"avg_confidence":0.955,"time_window":"60s","metrics":{"flows_per_second":25.0,"unique_sources":3,"avg_packet_size":512.5},"recommendation":"Consider blocking source IPs and enabling rate limiting"}'

echo "📤 Sending test alert to Kafka topic 'ddos-alerts'..."
echo ""
echo "Alert content:"
echo "$TEST_ALERT" | jq .
echo ""

# Send to Kafka
echo "$TEST_ALERT" | docker exec -i ids_kafka kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic ddos-alerts

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Test alert sent successfully!"
    echo ""
    echo "📱 Check your Telegram for the notification"
    echo ""
    echo "To verify:"
    echo "1. Check telegram-notifier logs: docker logs -f telegram-notifier"
    echo "2. View metrics: curl http://localhost:8005/metrics | grep telegram_alerts"
else
    echo ""
    echo "❌ Failed to send test alert"
    exit 1
fi
