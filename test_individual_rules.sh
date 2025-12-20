#!/bin/bash

# Script để test từng rule riêng biệt
# Điều chỉnh số lượng source IPs để tránh trigger AGG-008

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         Individual Rule Testing Helper                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

show_menu() {
    echo -e "${YELLOW}Select which rule to test:${NC}"
    echo ""
    echo "  1) AGG-001 (SYN Flood) - WITHOUT triggering AGG-008"
    echo "  2) AGG-002 (UDP Flood) - WITHOUT triggering AGG-008"
    echo "  3) AGG-008 (Distributed Attack) - ONLY this rule"
    echo "  4) Full attack (triggers multiple rules)"
    echo "  5) View current rule thresholds"
    echo "  6) Exit"
    echo ""
}

view_thresholds() {
    echo -e "${BLUE}Current Rule Thresholds:${NC}"
    echo ""
    echo "AGG-001 (SYN Flood):"
    echo "  - syn_flag_count > 500"
    echo "  - syn_ack_ratio > 0.8"
    echo "  - window: 30s"
    echo ""
    echo "AGG-002 (UDP Flood):"
    echo "  - udp_packet_count > 10,000"
    echo "  - window: 60s"
    echo ""
    echo "AGG-008 (Distributed Attack):"
    echo "  - unique_src_ips > 200"
    echo "  - flows_per_ip < 10"
    echo "  - window: 60s"
    echo ""
    echo -e "${YELLOW}Key insight:${NC}"
    echo "  To avoid triggering AGG-008, use < 200 source IPs"
    echo ""
}

test_syn_flood_only() {
    echo -e "${GREEN}Testing AGG-001 (SYN Flood) only...${NC}"
    echo ""
    echo "Configuration:"
    echo "  - Target: 192.168.241.2"
    echo "  - Port: 80"
    echo "  - Packets: 10,000"
    echo "  - Source IPs: 150 (< 200 to avoid AGG-008)"
    echo ""
    echo -e "${YELLOW}Expected result:${NC}"
    echo "  ✅ AGG-001 should trigger (SYN Flood)"
    echo "  ❌ AGG-008 should NOT trigger (< 200 IPs)"
    echo ""
    read -p "Press Enter to start attack..."
    
    cd src/scripts
    python3 -m ddos_attacks syn-flood \
        --target 192.168.241.2 \
        --port 80 \
        --num-packets 10000 \
        --num-sources 150 \
        --duration 30
    
    echo ""
    echo -e "${GREEN}Attack completed. Check alerts in ~30 seconds.${NC}"
}

test_udp_flood_only() {
    echo -e "${GREEN}Testing AGG-002 (UDP Flood) only...${NC}"
    echo ""
    echo "Configuration:"
    echo "  - Target: 192.168.241.2"
    echo "  - Port: 53 (DNS)"
    echo "  - Packets: 50,000"
    echo "  - Source IPs: 150 (< 200 to avoid AGG-008)"
    echo ""
    echo -e "${YELLOW}Expected result:${NC}"
    echo "  ✅ AGG-002 should trigger (UDP Flood)"
    echo "  ❌ AGG-008 should NOT trigger (< 200 IPs)"
    echo ""
    read -p "Press Enter to start attack..."
    
    cd src/scripts
    python3 -m ddos_attacks udp-flood \
        --target 192.168.241.2 \
        --port 53 \
        --num-packets 50000 \
        --num-sources 150 \
        --duration 60
    
    echo ""
    echo -e "${GREEN}Attack completed. Check alerts in ~60 seconds.${NC}"
}

test_distributed_only() {
    echo -e "${GREEN}Testing AGG-008 (Distributed Attack) only...${NC}"
    echo ""
    echo "Configuration:"
    echo "  - Target: 192.168.241.2"
    echo "  - Packets: 5,000 (low volume)"
    echo "  - Source IPs: 500 (> 200 to trigger AGG-008)"
    echo "  - Packets per source: 10 (low rate)"
    echo ""
    echo -e "${YELLOW}Expected result:${NC}"
    echo "  ✅ AGG-008 should trigger (Distributed pattern)"
    echo "  ❌ AGG-001/002 should NOT trigger (not enough packets)"
    echo ""
    read -p "Press Enter to start attack..."
    
    cd src/scripts
    python3 -m ddos_attacks distributed \
        --target 192.168.241.2 \
        --num-packets 5000 \
        --num-sources 500 \
        --duration 60
    
    echo ""
    echo -e "${GREEN}Attack completed. Check alerts in ~60 seconds.${NC}"
}

test_full_attack() {
    echo -e "${GREEN}Testing Full Attack (multiple rules)...${NC}"
    echo ""
    echo "Configuration:"
    echo "  - Target: 192.168.241.2"
    echo "  - Packets: 50,000"
    echo "  - Source IPs: 1,000 (distributed)"
    echo ""
    echo -e "${YELLOW}Expected result:${NC}"
    echo "  ✅ AGG-008 triggers first (~5-10s)"
    echo "  ✅ AGG-002 or AGG-001 triggers later (~20-30s)"
    echo ""
    read -p "Press Enter to start attack..."
    
    cd src/scripts
    python3 -m ddos_attacks udp-flood \
        --target 192.168.241.2 \
        --port 53 \
        --num-packets 50000 \
        --num-sources 1000 \
        --duration 60
    
    echo ""
    echo -e "${GREEN}Attack completed. Check alerts in ~60 seconds.${NC}"
}

monitor_alerts() {
    echo ""
    echo -e "${BLUE}Monitoring alerts (Ctrl+C to stop)...${NC}"
    echo ""
    
    # Monitor both detector and telegram logs
    docker logs -f ids_rule_detector 2>&1 | grep --line-buffered "ALERT" &
    PID1=$!
    
    docker logs -f telegram-notifier 2>&1 | grep --line-buffered -E "(Sent:|Suppressed:)" &
    PID2=$!
    
    # Wait for user to stop
    trap "kill $PID1 $PID2 2>/dev/null" EXIT
    wait
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice [1-6]: " choice
    echo ""
    
    case $choice in
        1)
            test_syn_flood_only
            echo ""
            read -p "Monitor alerts now? (y/n): " monitor
            if [ "$monitor" = "y" ]; then
                monitor_alerts
            fi
            ;;
        2)
            test_udp_flood_only
            echo ""
            read -p "Monitor alerts now? (y/n): " monitor
            if [ "$monitor" = "y" ]; then
                monitor_alerts
            fi
            ;;
        3)
            test_distributed_only
            echo ""
            read -p "Monitor alerts now? (y/n): " monitor
            if [ "$monitor" = "y" ]; then
                monitor_alerts
            fi
            ;;
        4)
            test_full_attack
            echo ""
            read -p "Monitor alerts now? (y/n): " monitor
            if [ "$monitor" = "y" ]; then
                monitor_alerts
            fi
            ;;
        5)
            view_thresholds
            ;;
        6)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please try again.${NC}"
            ;;
    esac
    
    echo ""
    echo "─────────────────────────────────────────────────────────────"
    echo ""
done
