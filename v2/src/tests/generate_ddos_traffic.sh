#!/bin/bash

###############################################################################
# DDoS Traffic Generator for Testing
# Tạo traffic để test DDoS detection system
###############################################################################

TARGET_URL="${1:-http://localhost:8080}"
RATE="${2:-100}"  # requests per second
DURATION="${3:-60}"  # seconds

echo "🚀 Starting DDoS Traffic Generator"
echo "   Target: $TARGET_URL"
echo "   Rate: $RATE req/s"
echo "   Duration: $DURATION seconds"
echo ""

# Check if apache bench is installed
if ! command -v ab &> /dev/null; then
    echo "❌ Apache Bench (ab) is not installed"
    echo "   Install: sudo apt-get install apache2-utils"
    exit 1
fi

# Calculate total requests
TOTAL_REQUESTS=$((RATE * DURATION))
CONCURRENT=$((RATE / 10))

echo "📊 Total requests: $TOTAL_REQUESTS"
echo "📊 Concurrent connections: $CONCURRENT"
echo ""

echo "⏱️  Starting in 3 seconds..."
sleep 3

echo "🔥 Generating traffic..."
ab -n "$TOTAL_REQUESTS" -c "$CONCURRENT" -t "$DURATION" "$TARGET_URL/" 2>&1 | grep -E "Requests per second|Time per request|Failed requests"

echo ""
echo "✅ Traffic generation complete!"
echo ""
echo "📊 Check results:"
echo "   - Grafana: http://localhost:3000"
echo "   - Prometheus: http://localhost:9090"
echo "   - DDoS Alerts: docker exec ids_kafka kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic ddos-alerts --from-beginning"
echo ""
echo "💡 View metrics:"
echo "   curl http://localhost:8001/metrics | grep ddos_alerts"
