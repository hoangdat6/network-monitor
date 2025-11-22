#!/bin/bash

set -e

# Color codes and logging functions (define first)
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log(){ echo -e "${GREEN}[$(date '+%F %T')]${NC} $*"; }
warn(){ echo -e "${YELLOW}[$(date '+%F %T')] WARNING:${NC} $*"; }
err(){ echo -e "${RED}[$(date '+%F %T')] ERROR:${NC} $*"; }

# === Config ===
INTERFACE=${INTERFACE:-"wlp1s0"}
PCAP_DIR=${PCAP_DIR:-"/tmp/pcap"}
OUTPUT_DIR=${OUTPUT_DIR:-"/output"}
CAPTURE_INTERVAL=${CAPTURE_INTERVAL:-10}   # seconds per file

# Lọc traffic: loại bỏ SSH, NFS và local traffic
# Chỉ capture traffic từ bên ngoài vào server
LOCAL_IP=$(ip -4 addr show "$INTERFACE" 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
if [ -n "$LOCAL_IP" ]; then
    # Chỉ capture traffic đến server từ IP bên ngoài (src không phải local)
    FILTER_EXPR=${FILTER_EXPR:-"not port 22 and not port 2049 and dst host $LOCAL_IP and not src net 192.168.0.0/16 and not src net 10.0.0.0/8 and not src net 172.16.0.0/12"}
    log "Filtering: Only external IPs -> $LOCAL_IP"
else
    FILTER_EXPR=${FILTER_EXPR:-"not port 22 and not port 2049"}
    warn "Could not detect local IP, using basic filter"
fi

mkdir -p "$PCAP_DIR" "$OUTPUT_DIR"

# === Health Check ===
health_check() {
    log "=== CICFlowMeter Health Check ==="
    
    # Check interface
    if ! ip link show "$INTERFACE" >/dev/null 2>&1; then
        err "Interface $INTERFACE not found"
        log "Available interfaces:"
        ip link show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d ' ' | sed 's/^/  /'
        exit 1
    fi
    log "✓ Interface $INTERFACE available"
    
    # Check directories
    if [ ! -w "$OUTPUT_DIR" ]; then
        err "Cannot write to $OUTPUT_DIR"
        exit 1
    fi
    log "✓ Output directory writable"
    
    if [ ! -w "$PCAP_DIR" ]; then
        err "Cannot write to $PCAP_DIR"
        exit 1
    fi
    log "✓ PCAP directory writable"
    
    # Test tcpdump
    if timeout 2 tcpdump -i "$INTERFACE" -w /tmp/test.pcap -c 1 -Z root >/dev/null 2>&1; then
        log "✓ Packet capture test successful"
        rm -f /tmp/test.pcap
    else
        err "Cannot capture packets on $INTERFACE"
        exit 1
    fi
    
    log "=== Health check passed ==="
}

# === 1. Start continuous tcpdump ===
start_capture() {
    log "Starting continuous tcpdump rotation on $INTERFACE (every ${CAPTURE_INTERVAL}s)..."
    tcpdump -i "$INTERFACE" \
        -G "$CAPTURE_INTERVAL" \
        -w "$PCAP_DIR/capture_%Y%m%d_%H%M%S.pcap" \
        -s 0 -Z root \
        $FILTER_EXPR >/dev/null 2>&1 &
    echo $! > /tmp/tcpdump_pid
    log "tcpdump PID $(cat /tmp/tcpdump_pid)"
}

# === 2. Watch for new PCAPs and process ===
process_new_pcaps() {
    log "Watching $PCAP_DIR for new PCAPs..."
    inotifywait -m -e create "$PCAP_DIR" --format "%f" | while read -r file; do
        if [[ "$file" == *.pcap ]]; then
            local pcap_path="$PCAP_DIR/$file"
            local csv_path="$OUTPUT_DIR/${file%.pcap}.csv"
            log "🧩 New PCAP detected: $file → processing with CICFlowMeter..."

            # Run cicflowmeter
            if cicflowmeter -f "$pcap_path" -c "$csv_path" 2>/dev/null; then
                if [[ -s "$csv_path" ]]; then
                    local row_count
                    row_count=$(($(wc -l < "$csv_path") - 1))
                    log "✅ Extracted $row_count flows from $(basename "$pcap_path") → $(basename "$csv_path")"
                else
                    log "⚠️  CSV file empty → no flows extracted"
                fi
            else
                log "❌ CICFlowMeter failed for $file, skipping"
            fi

            # Cleanup pcap regardless
            rm -f "$pcap_path"
        fi
    done
}


# === 3. Cleanup old files ===
cleanup_loop() {
    while true; do
        find "$OUTPUT_DIR" -name "*.csv" -mmin +60 -delete
        find "$PCAP_DIR" -name "*.pcap" -mmin +10 -delete
        sleep 300
    done
}

# === Main ===
main() {
    case "$1" in
        start)
            log "Starting CICFlowMeter capture daemon..."
            start_capture
            process_new_pcaps &
            cleanup_loop &
            wait
            ;;
        stop)
            if [ -f /tmp/tcpdump_pid ]; then
                kill "$(cat /tmp/tcpdump_pid)" 2>/dev/null && log "Stopped tcpdump"
                rm -f /tmp/tcpdump_pid
            else
                log "No tcpdump PID file found"
            fi
            ;;
        health)
            health_check
            ;;
        *)
            echo "Usage: $0 {start|stop|health}"
            ;;
    esac
}

main "$@"
