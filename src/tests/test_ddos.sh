#!/bin/bash
# Simple DDoS Test Script using basic tools

set -e

TARGET="${1:-localhost}"
PORT="${2:-80}"
DURATION="${3:-30}"

echo "=========================================="
echo "🧪 DDoS Detection Test"
echo "=========================================="
echo "Target: $TARGET:$PORT"
echo "Duration: ${DURATION}s"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Note: Some tests require root/sudo"
fi

echo "Choose attack type:"
echo "1) Basic HTTP Flood (curl)"
echo "2) TCP SYN Flood (hping3 - requires root)"
echo "3) UDP Flood (hping3 - requires root)"
echo "4) Ping Flood (ping)"
echo "5) Multiple connections (ab)"
echo ""
read -p "Select (1-5): " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting HTTP Flood with curl..."
        echo "   Generating ~100 requests/second"
        echo ""
        
        END_TIME=$(($(date +%s) + $DURATION))
        COUNT=0
        
        while [ $(date +%s) -lt $END_TIME ]; do
            for i in {1..10}; do
                curl -s -o /dev/null "http://${TARGET}:${PORT}/" &
            done
            COUNT=$((COUNT + 10))
            sleep 0.1
            
            if [ $((COUNT % 100)) -eq 0 ]; then
                echo "Sent $COUNT requests..."
            fi
        done
        
        wait
        echo "✅ Completed: $COUNT total requests"
        ;;
        
    2)
        echo ""
        echo "🚀 Starting TCP SYN Flood..."
        
        if ! command -v hping3 &> /dev/null; then
            echo "❌ hping3 not found"
            echo "Install: sudo apt-get install hping3"
            exit 1
        fi
        
        sudo timeout ${DURATION}s hping3 -S --flood -p $PORT $TARGET
        echo "✅ Completed"
        ;;
        
    3)
        echo ""
        echo "🚀 Starting UDP Flood..."
        
        if ! command -v hping3 &> /dev/null; then
            echo "❌ hping3 not found"
            exit 1
        fi
        
        sudo timeout ${DURATION}s hping3 --udp --flood -p $PORT $TARGET
        echo "✅ Completed"
        ;;
        
    4)
        echo ""
        echo "🚀 Starting Ping Flood..."
        echo "   Sending ICMP packets rapidly"
        
        sudo timeout ${DURATION}s ping -f $TARGET
        echo "✅ Completed"
        ;;
        
    5)
        echo ""
        echo "🚀 Starting Apache Bench test..."
        
        if ! command -v ab &> /dev/null; then
            echo "❌ ab not found"
            echo "Install: sudo apt-get install apache2-utils"
            exit 1
        fi
        
        TOTAL=$((DURATION * 100))
        ab -n $TOTAL -c 50 "http://${TARGET}:${PORT}/"
        echo "✅ Completed"
        ;;
        
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "📊 Check Detection Results:"
echo "=========================================="
echo ""
echo "1. View DDoS alerts:"
echo "   docker exec -it ids_kafka kafka-console-consumer.sh \\"
echo "     --bootstrap-server localhost:9092 \\"
echo "     --topic ddos-alerts --from-beginning"
echo ""
echo "2. Check detector logs:"
echo "   docker logs ids_ddos_detector | grep -i suspicious"
echo ""
echo "3. View metrics:"
echo "   curl http://localhost:8001/metrics | grep ddos"
echo ""
echo "4. Check flows in Kafka:"
echo "   docker exec -it ids_kafka kafka-console-consumer.sh \\"
echo "     --bootstrap-server localhost:9092 \\"
echo "     --topic network-flows --max-messages 10"
echo ""
