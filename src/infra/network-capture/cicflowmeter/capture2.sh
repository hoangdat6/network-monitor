#!/bin/bash
# ==========================================
# CICFlowMeter Continuous Capture (Zero-Miss)
# ==========================================

set -e

# === Config ===
INTERFACE=${INTERFACE:-"enp3s0"}
PCAP_DIR=${PCAP_DIR:-"/tmp/pcap"}
OUTPUT_DIR=${OUTPUT_DIR:-"/output"}
CAPTURE_INTERVAL=${CAPTURE_INTERVAL:-60}   # seconds per file
FILTER_EXPR=${FILTER_EXPR:-"not port 22 and not port 2049"} # avoid SSH/NFS noise

mkdir -p "$PCAP_DIR" "$OUTPUT_DIR"

log() { echo "[$(date '+%F %T')] $*"; }

# === 1. Start continuous tcpdump ===
start_capture() {
    log "Starting continuous tcpdump rotation on $INTERFACE (every ${CAPTURE_INTERVAL}s)..."
    sudo tcpdump -i "$INTERFACE" \
        -G "$CAPTURE_INTERVAL" \
        -w "$PCAP_DIR/capture_%Y%m%d_%H%M%S.pcap" \
        -s 0 -Z nobody \
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
            log "New pcap detected: $file → Processing..."
            
            if command -v cicflowmeter >/dev/null 2>&1; then
                cicflowmeter -f "$pcap_path" -c "$csv_path" 2>/dev/null && \
                    log "✅ Converted: $csv_path"
            elif [ -f "/app/CICFlowMeter.jar" ]; then
                java -jar /app/CICFlowMeter.jar "$pcap_path" "$csv_path" 2>/dev/null && \
                    log "✅ Converted: $csv_path"
            else
                log "❌ CICFlowMeter not found"
                continue
            fi

            rm -f "$pcap_path"   # cleanup after processing
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
        *)
            echo "Usage: $0 {start|stop}"
            ;;
    esac
}

main "$@"
