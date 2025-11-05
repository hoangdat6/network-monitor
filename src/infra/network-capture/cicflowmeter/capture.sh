#!/bin/bash

# CICFlowMeter Capture Script
# 
# Mục đích: Capture network packets và convert sang CSV với 78 features
# Tại sao script: CICFlowMeter cần chạy batch mode để tránh memory leak
# Cách khác: Real-time processing nhưng kém stable với high traffic
# Bản chất: tcpdump -> pcap -> CICFlowMeter -> CSV -> Kafka

set -e

# Configuration
INTERFACE=${INTERFACE:-"enp3s0"}
CAPTURE_DURATION=${CAPTURE_DURATION:-60}  # seconds
OUTPUT_DIR=${OUTPUT_DIR:-"/output"}
PCAP_DIR=${PCAP_DIR:-"/tmp/pcap"}
MAX_PCAP_SIZE=${MAX_PCAP_SIZE:-"100M"}
KAFKA_TOPIC=${KAFKA_TOPIC:-"network-flows"}

# Ensure directories exist
mkdir -p "$OUTPUT_DIR" "$PCAP_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

cleanup() {
    log "Cleaning up old PCAP files..."
    find "$PCAP_DIR" -name "*.pcap" -mmin +30 -delete
    find "$OUTPUT_DIR" -name "*.csv" -mmin +60 -delete
}

capture_traffic() {
    local timestamp=$(date +%s)
    local pcap_file="$PCAP_DIR/capture_${timestamp}.pcap"
    local csv_file="$OUTPUT_DIR/flows_${timestamp}.csv"
    
    log "Starting packet capture for ${CAPTURE_DURATION}s on interface $INTERFACE"
    
    # Capture packets với size limit
    timeout "$CAPTURE_DURATION" tcpdump -i "$INTERFACE" \
        -w "$pcap_file" \
        -C 100 \
        -Z nobody \
        -s 0 \
        'not port 22 and not port 2049' \
        || true  # timeout is expected
    
    if [ ! -f "$pcap_file" ] || [ ! -s "$pcap_file" ]; then
        log "No packets captured or file empty"
        return 1
    fi
    
    log "Captured $(du -h "$pcap_file" | cut -f1) of traffic"
    
    # Convert PCAP to flows using CICFlowMeter
    log "Converting PCAP to flows..."
    
    if command -v cicflowmeter >/dev/null 2>&1; then
        # Python CICFlowMeter
        cicflowmeter -f "$pcap_file" -c "$csv_file" 2>/dev/null || {
            log "CICFlowMeter failed, skipping file"
            rm -f "$pcap_file"
            return 1
        }
    elif [ -f "/app/CICFlowMeter.jar" ]; then
        # Java CICFlowMeter  
        java -jar /app/CICFlowMeter.jar "$pcap_file" "$csv_file" 2>/dev/null || {
            log "Java CICFlowMeter failed, skipping file"
            rm -f "$pcap_file"
            return 1
        }
    else
        log "No CICFlowMeter found, cannot process PCAP"
        rm -f "$pcap_file"
        return 1
    fi
    
    if [ ! -f "$csv_file" ] || [ ! -s "$csv_file" ]; then
        log "Flow extraction failed or empty result"
        rm -f "$pcap_file"
        return 1
    fi
    
    local flow_count=$(wc -l < "$csv_file")
    log "Extracted $flow_count flows to $csv_file"
    
    # Validate CSV format
    if ! validate_csv "$csv_file"; then
        log "CSV validation failed, removing file"
        rm -f "$csv_file" "$pcap_file"
        return 1
    fi
    
    # Clean up PCAP file
    rm -f "$pcap_file"
    
    return 0
}

validate_csv() {
    local csv_file="$1"
    
    # Check if file has header and data
    local line_count=$(wc -l < "$csv_file")
    if [ "$line_count" -lt 2 ]; then
        log "CSV has no data rows"
        return 1
    fi
    
    # Check for critical columns
    local header=$(head -n 1 "$csv_file")
    local required_cols=("flow_duration" "tot_fwd_pkts" "tot_bwd_pkts" "flow_pkts_s")
    
    for col in "${required_cols[@]}"; do
        if ! echo "$header" | grep -q "$col"; then
            log "Missing required column: $col"
            return 1
        fi
    done
    
    log "CSV validation passed"
    return 0
}

# Health check function
health_check() {
    echo "CICFlowMeter Health Check"
    echo "========================"
    echo "Interface: $INTERFACE"
    echo "Output Dir: $OUTPUT_DIR"
    echo "PCAP Dir: $PCAP_DIR"
    echo "Capture Duration: ${CAPTURE_DURATION}s"
    
    # Check interface exists
    if ! ip link show "$INTERFACE" >/dev/null 2>&1; then
        echo "ERROR: Interface $INTERFACE not found"
        exit 1
    fi
    
    # Check permissions
    if ! touch "$OUTPUT_DIR/test" 2>/dev/null; then
        echo "ERROR: Cannot write to $OUTPUT_DIR"
        exit 1
    fi
    rm -f "$OUTPUT_DIR/test"
    
    # Check CICFlowMeter
    if command -v cicflowmeter >/dev/null 2>&1; then
        echo "CICFlowMeter: Python version found"
    elif [ -f "/app/CICFlowMeter.jar" ]; then
        echo "CICFlowMeter: Java version found"
    else
        echo "ERROR: No CICFlowMeter found"
        exit 1
    fi
    
    echo "Health check passed"
}

main() {
    case "${1:-capture}" in
        "health")
            health_check
            ;;
        "cleanup")
            cleanup
            ;;
        "capture")
            log "Starting CICFlowMeter capture daemon"
            while true; do
                capture_traffic || log "Capture cycle failed, continuing..."
                cleanup
                sleep 5  # Brief pause between captures
            done
            ;;
        *)
            echo "Usage: $0 [capture|health|cleanup]"
            exit 1
            ;;
    esac
}

# Handle signals
trap 'log "Received signal, shutting down..."; exit 0' SIGTERM SIGINT

main "$@"