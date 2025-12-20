#!/bin/bash

# Alert Monitoring and Debugging Script
# Kiểm tra trạng thái alerts và metrics

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Alert Monitoring & Debugging Tool                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print section header
print_section() {
    echo -e "\n${YELLOW}━━━ $1 ━━━${NC}\n"
}

# Function to check if container is running
check_container() {
    local container=$1
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        echo -e "${GREEN}✓${NC} $container is running"
        return 0
    else
        echo -e "${RED}✗${NC} $container is NOT running"
        return 1
    fi
}

# 1. Check Container Status
print_section "1. Container Status"
check_container "ids_rule_detector"
check_container "telegram-notifier"
check_container "prometheus"
check_container "grafana"
check_container "ids_kafka"

# 2. Check Telegram Notifier Metrics
print_section "2. Telegram Notifier Metrics"
if curl -s http://localhost:8005/metrics > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Telegram Notifier metrics endpoint is accessible"
    echo ""
    
    # Parse metrics
    ALERTS_RECEIVED=$(curl -s http://localhost:8005/metrics | grep 'telegram_alerts_received_total{' | awk '{sum+=$2} END {print sum}')
    ALERTS_SENT=$(curl -s http://localhost:8005/metrics | grep 'telegram_alerts_sent_total{' | awk '{sum+=$2} END {print sum}')
    ALERTS_SUPPRESSED=$(curl -s http://localhost:8005/metrics | grep 'telegram_alerts_suppressed_total{' | awk '{sum+=$2} END {print sum}')
    ALERTS_AGGREGATED=$(curl -s http://localhost:8005/metrics | grep 'telegram_alerts_aggregated_total' | grep -v '#' | awk '{print $2}')
    
    echo "  📥 Alerts Received:   ${ALERTS_RECEIVED:-0}"
    echo "  ✅ Alerts Sent:       ${ALERTS_SENT:-0}"
    echo "  ⚠️  Alerts Suppressed: ${ALERTS_SUPPRESSED:-0}"
    echo "  📊 Alerts Aggregated: ${ALERTS_AGGREGATED:-0}"
    
    if [ "${ALERTS_SUPPRESSED:-0}" -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}⚠️  Warning: ${ALERTS_SUPPRESSED} alerts were suppressed!${NC}"
        echo "  Reasons:"
        curl -s http://localhost:8005/metrics | grep 'telegram_alerts_suppressed_total{' | while read line; do
            reason=$(echo $line | grep -o 'reason="[^"]*"' | cut -d'"' -f2)
            count=$(echo $line | awk '{print $2}')
            echo "    - $reason: $count"
        done
    fi
else
    echo -e "${RED}✗${NC} Cannot access Telegram Notifier metrics"
fi

# 3. Check Rule-Based Detector Metrics
print_section "3. Rule-Based Detector Metrics"
if curl -s http://localhost:8002/metrics > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Rule-Based Detector metrics endpoint is accessible"
    echo ""
    
    TOTAL_ALERTS=$(curl -s http://localhost:8002/metrics | grep 'rule_detector_alerts_total{' | awk '{sum+=$2} END {print sum}')
    FLOWS_PROCESSED=$(curl -s http://localhost:8002/metrics | grep 'rule_detector_flows_processed_total' | grep -v '#' | awk '{print $2}')
    
    echo "  🚨 Total Alerts Triggered: ${TOTAL_ALERTS:-0}"
    echo "  📊 Total Flows Processed:  ${FLOWS_PROCESSED:-0}"
    echo ""
    echo "  Alerts by Rule:"
    curl -s http://localhost:8002/metrics | grep 'rule_detector_alerts_total{' | while read line; do
        rule_id=$(echo $line | grep -o 'rule_id="[^"]*"' | cut -d'"' -f2)
        severity=$(echo $line | grep -o 'severity="[^"]*"' | cut -d'"' -f2)
        count=$(echo $line | awk '{print $2}')
        printf "    %-10s [%-8s]: %s\n" "$rule_id" "$severity" "$count"
    done
else
    echo -e "${RED}✗${NC} Cannot access Rule-Based Detector metrics"
fi

# 4. Check Prometheus
print_section "4. Prometheus Status"
if curl -s http://localhost:9099/api/v1/targets > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Prometheus is accessible"
    
    # Check if rule-based-detector target is up
    DETECTOR_STATUS=$(curl -s http://localhost:9099/api/v1/targets | python3 -c "
import sys, json
data = json.load(sys.stdin)
for target in data['data']['activeTargets']:
    if target['labels']['job'] == 'rule-based-detector':
        print(target['health'])
        break
" 2>/dev/null || echo "unknown")
    
    if [ "$DETECTOR_STATUS" = "up" ]; then
        echo -e "  ${GREEN}✓${NC} rule-based-detector target is UP"
    else
        echo -e "  ${RED}✗${NC} rule-based-detector target is DOWN or not found"
    fi
    
    # Check if metrics are available
    METRICS_COUNT=$(curl -s 'http://localhost:9099/api/v1/query?query=rule_detector_alerts_total' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(len(data['data']['result']))
" 2>/dev/null || echo "0")
    
    echo "  📊 Metrics available: $METRICS_COUNT series"
else
    echo -e "${RED}✗${NC} Cannot access Prometheus"
fi

# 5. Check Grafana
print_section "5. Grafana Status"
if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Grafana is accessible"
    
    # Check datasource
    DATASOURCE_STATUS=$(curl -s -u admin:admin http://localhost:3000/api/datasources | python3 -c "
import sys, json
data = json.load(sys.stdin)
for ds in data:
    if ds['type'] == 'prometheus':
        print('configured')
        break
else:
    print('not_found')
" 2>/dev/null || echo "error")
    
    if [ "$DATASOURCE_STATUS" = "configured" ]; then
        echo -e "  ${GREEN}✓${NC} Prometheus datasource is configured"
    else
        echo -e "  ${RED}✗${NC} Prometheus datasource not found"
    fi
    
    echo "  🌐 Dashboard URL: http://localhost:3000/d/rule-based-detector"
else
    echo -e "${RED}✗${NC} Cannot access Grafana"
fi

# 6. Check Recent Alerts in Kafka
print_section "6. Recent Alerts in Kafka (Last 3)"
if docker exec ids_kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic ddos-alerts \
    --from-beginning \
    --max-messages 3 \
    --timeout-ms 5000 2>/dev/null | while read line; do
        echo "$line" | python3 -c "
import sys, json
try:
    alert = json.load(sys.stdin)
    print(f\"  🚨 [{alert.get('severity', 'N/A').upper()}] {alert.get('rule_name', 'Unknown')} - {alert.get('timestamp', 'N/A')}\")
    print(f\"     Alert ID: {alert.get('alert_id', 'N/A')}\")
    print(f\"     Attackers: {len(alert.get('attacker_ips', []))} IPs\")
    print()
except:
    pass
" 2>/dev/null
    done; then
    :
else
    echo -e "${RED}✗${NC} Cannot read from Kafka topic"
fi

# 7. Check Current Anti-Spam Configuration
print_section "7. Current Anti-Spam Configuration"
echo "  Reading from docker-compose.monitoring.yml..."
echo ""

if [ -f "src/docker-compose.monitoring.yml" ]; then
    grep -A 5 "Anti-spam Configuration" src/docker-compose.monitoring.yml | grep -E "MIN_ALERT_INTERVAL|MAX_ALERTS_PER_WINDOW|RATE_LIMIT_WINDOW|AGGREGATION_WINDOW|COOLDOWN_AFTER_BURST" | while read line; do
        echo "  $line"
    done
else
    echo -e "${RED}✗${NC} docker-compose.monitoring.yml not found"
fi

# 8. Recent Logs
print_section "8. Recent Telegram Notifier Logs (Last 10 lines)"
docker logs telegram-notifier --tail 10 2>/dev/null | while read line; do
    if echo "$line" | grep -q "Sent:"; then
        echo -e "  ${GREEN}$line${NC}"
    elif echo "$line" | grep -q "Suppressed:"; then
        echo -e "  ${YELLOW}$line${NC}"
    elif echo "$line" | grep -q "ERROR"; then
        echo -e "  ${RED}$line${NC}"
    else
        echo "  $line"
    fi
done

# Summary
print_section "Summary & Recommendations"

TOTAL_RECEIVED=${ALERTS_RECEIVED:-0}
TOTAL_SENT=${ALERTS_SENT:-0}
TOTAL_SUPPRESSED=${ALERTS_SUPPRESSED:-0}

if [ "$TOTAL_SUPPRESSED" -gt 0 ]; then
    SUPPRESS_RATE=$(echo "scale=1; $TOTAL_SUPPRESSED * 100 / $TOTAL_RECEIVED" | bc 2>/dev/null || echo "N/A")
    echo -e "${YELLOW}⚠️  Alert Suppression Rate: ${SUPPRESS_RATE}%${NC}"
    echo ""
    echo "Recommendations:"
    echo "  1. Consider reducing MIN_ALERT_INTERVAL (current: 60s)"
    echo "  2. Consider increasing MAX_ALERTS_PER_WINDOW (current: 5)"
    echo "  3. Check alert summaries in Telegram for aggregated alerts"
    echo ""
    echo "To adjust settings:"
    echo "  1. Edit: src/docker-compose.monitoring.yml"
    echo "  2. Restart: docker restart telegram-notifier"
else
    echo -e "${GREEN}✓${NC} All alerts are being sent successfully!"
fi

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "For detailed troubleshooting, see: ALERT_TROUBLESHOOTING.md"
echo ""
