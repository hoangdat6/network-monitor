#!/bin/bash

###############################################################################
# Network Monitor System Control Script
# 
# Quản lý toàn bộ hệ thống IDS/IPS với DDoS Detection
# - Data Pipeline (Kafka, Zookeeper)
# - Network Capture & Detection (CICFlowMeter, Flow Processor, DDoS Detector)
# - Monitoring Stack (Prometheus, Grafana, cAdvisor, Node Exporter)
# - Nginx Web Server
# - Metrics Processing (Prometheus-Kafka Adapter, Metrics Flattener)
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Docker compose files
COMPOSE_DATA_PIPELINE="docker-compose.data-pipeline.yml"
COMPOSE_NETWORK="docker-compose.network.yml"
COMPOSE_MONITORING="docker-compose.monitoring.yml"
COMPOSE_NGINX="docker-compose.nginx.yml"
COMPOSE_PROM_METRIC="docker-compose.prom-metric.yml"

# Network name
NETWORK_NAME="ids-network"

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "${BLUE}===================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}===================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker không được cài đặt"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker daemon không chạy hoặc không có quyền truy cập"
        exit 1
    fi
    
    print_success "Docker đã sẵn sàng"
}

check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose không được cài đặt"
        exit 1
    fi
    print_success "Docker Compose đã sẵn sàng"
}

create_network() {
    if docker network ls | grep -q "$NETWORK_NAME"; then
        print_info "Network $NETWORK_NAME đã tồn tại"
    else
        docker network create "$NETWORK_NAME"
        print_success "Đã tạo network $NETWORK_NAME"
    fi
}

create_volumes() {
    print_info "Tạo Docker volumes..."
    
    volumes=(
        "network_flows"
        "pcap_data"
        "processed_flows"
        "prometheus_data"
        "grafana_data"
        "nginx_logs"
    )
    
    for volume in "${volumes[@]}"; do
        if docker volume ls | grep -q "$volume"; then
            print_info "Volume $volume đã tồn tại"
        else
            docker volume create "$volume"
            print_success "Đã tạo volume $volume"
        fi
    done
}

wait_for_service() {
    local service_name=$1
    local max_attempts=${2:-30}
    local attempt=1
    
    print_info "Đợi $service_name khởi động..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker ps --filter "name=$service_name" --filter "status=running" | grep -q "$service_name"; then
            print_success "$service_name đã sẵn sàng"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_warning "$service_name mất nhiều thời gian để khởi động"
    return 1
}

check_service_health() {
    local service_name=$1
    local url=$2
    local max_attempts=${3:-15}
    local attempt=1
    
    print_info "Kiểm tra health của $service_name..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            print_success "$service_name health check OK"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_warning "$service_name health check không thành công"
    return 1
}

###############################################################################
# Start Functions
###############################################################################

start_data_pipeline() {
    print_header "KHỞI ĐỘNG DATA PIPELINE (Kafka, Zookeeper)"
    
    docker-compose -f "$COMPOSE_DATA_PIPELINE" up -d
    
    wait_for_service "ids_zookeeper" 20
    wait_for_service "ids_kafka" 30
    
    sleep 5
    print_success "Data pipeline đã khởi động"
}

start_monitoring() {
    print_header "KHỞI ĐỘNG MONITORING STACK (Prometheus, Grafana, cAdvisor, Node Exporter)"
    
    docker-compose -f "$COMPOSE_MONITORING" up -d
    
    wait_for_service "prometheus" 20
    wait_for_service "node-exporter" 10
    wait_for_service "cadvisor" 10
    wait_for_service "grafana" 20
    
    check_service_health "Prometheus" "http://localhost:9090/-/healthy"
    check_service_health "Grafana" "http://localhost:3000/api/health"
    
    print_success "Monitoring stack đã khởi động"
}

start_network_detection() {
    print_header "KHỞI ĐỘNG NETWORK DETECTION (CICFlowMeter, Flow Processor, DDoS Detector)"
    
    docker-compose -f "$COMPOSE_NETWORK" up -d
    
    wait_for_service "ids_cicflowmeter" 15
    wait_for_service "ids_flow_processor" 15
    wait_for_service "ids_ddos_detector" 20
    
    check_service_health "DDoS Detector" "http://localhost:8001/metrics"
    
    print_success "Network detection đã khởi động"
}

start_nginx() {
    print_header "KHỞI ĐỘNG NGINX WEB SERVER"
    
    docker-compose -f "$COMPOSE_NGINX" up -d
    
    wait_for_service "nginx" 10
    check_service_health "Nginx" "http://localhost:8080"
    
    print_success "Nginx đã khởi động"
}

start_metrics_processing() {
    print_header "KHỞI ĐỘNG METRICS PROCESSING (Prometheus-Kafka Adapter, Metrics Flattener)"
    
    docker-compose -f "$COMPOSE_PROM_METRIC" up -d
    
    wait_for_service "ids_prometheus_kafka_adapter" 15
    wait_for_service "metrics-flattener" 15
    
    print_success "Metrics processing đã khởi động"
}

start_all() {
    print_header "KHỞI ĐỘNG TOÀN BỘ HỆ THỐNG"
    
    check_docker
    check_docker_compose
    create_network
    create_volumes
    
    echo ""
    start_data_pipeline
    echo ""
    sleep 10
    
    start_monitoring
    echo ""
    sleep 5
    
    start_network_detection
    echo ""
    sleep 5
    
    start_nginx
    echo ""
    
    start_metrics_processing
    echo ""
    
    print_header "HỆ THỐNG ĐÃ KHỞI ĐỘNG HOÀN TẤT"
    show_status
    show_urls
}

###############################################################################
# Stop Functions
###############################################################################

stop_all() {
    print_header "DỪNG TOÀN BỘ HỆ THỐNG"
    
    print_info "Dừng Metrics Processing..."
    docker-compose -f "$COMPOSE_PROM_METRIC" down
    
    print_info "Dừng Nginx..."
    docker-compose -f "$COMPOSE_NGINX" down
    
    print_info "Dừng Network Detection..."
    docker-compose -f "$COMPOSE_NETWORK" down
    
    print_info "Dừng Monitoring..."
    docker-compose -f "$COMPOSE_MONITORING" down
    
    print_info "Dừng Data Pipeline..."
    docker-compose -f "$COMPOSE_DATA_PIPELINE" down
    
    print_success "Toàn bộ hệ thống đã dừng"
}

stop_all_remove() {
    print_header "DỪNG VÀ XÓA TOÀN BỘ HỆ THỐNG"
    
    print_warning "Cảnh báo: Thao tác này sẽ xóa containers, volumes và data!"
    read -p "Bạn có chắc chắn? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "Đã hủy"
        exit 0
    fi
    
    docker-compose -f "$COMPOSE_PROM_METRIC" down -v
    docker-compose -f "$COMPOSE_NGINX" down -v
    docker-compose -f "$COMPOSE_NETWORK" down -v
    docker-compose -f "$COMPOSE_MONITORING" down -v
    docker-compose -f "$COMPOSE_DATA_PIPELINE" down -v
    
    print_success "Đã xóa toàn bộ hệ thống và data"
}

###############################################################################
# Restart Functions
###############################################################################

restart_all() {
    print_header "KHỞI ĐỘNG LẠI TOÀN BỘ HỆ THỐNG"
    stop_all
    sleep 5
    start_all
}

restart_service() {
    local service=$1
    
    case $service in
        data-pipeline|kafka)
            print_info "Khởi động lại Data Pipeline..."
            docker-compose -f "$COMPOSE_DATA_PIPELINE" restart
            ;;
        network|detection|ddos)
            print_info "Khởi động lại Network Detection..."
            docker-compose -f "$COMPOSE_NETWORK" restart
            ;;
        monitoring|prometheus|grafana)
            print_info "Khởi động lại Monitoring..."
            docker-compose -f "$COMPOSE_MONITORING" restart
            ;;
        nginx)
            print_info "Khởi động lại Nginx..."
            docker-compose -f "$COMPOSE_NGINX" restart
            ;;
        metrics)
            print_info "Khởi động lại Metrics Processing..."
            docker-compose -f "$COMPOSE_PROM_METRIC" restart
            ;;
        *)
            print_error "Service không hợp lệ: $service"
            print_info "Các service có sẵn: data-pipeline, network, monitoring, nginx, metrics"
            exit 1
            ;;
    esac
    
    print_success "Service $service đã khởi động lại"
}

###############################################################################
# Status Functions
###############################################################################

show_status() {
    print_header "TRẠNG THÁI HỆ THỐNG"
    
    echo -e "${BLUE}Container Status:${NC}"
    docker ps --filter "network=ids-network" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|ids_|prometheus|grafana|cadvisor|node-exporter|nginx|metrics"
    
    echo ""
    echo -e "${BLUE}Network:${NC}"
    docker network inspect "$NETWORK_NAME" --format "Network: {{.Name}} - Containers: {{len .Containers}}" 2>/dev/null || echo "Network chưa tạo"
    
    echo ""
    echo -e "${BLUE}Volumes:${NC}"
    docker volume ls --filter "name=network_flows|pcap_data|prometheus_data|grafana_data|nginx_logs" --format "table {{.Name}}\t{{.Driver}}"
}

show_logs() {
    local service=$1
    local lines=${2:-50}
    
    if [ -z "$service" ]; then
        print_error "Vui lòng chỉ định service"
        print_info "Ví dụ: $0 logs ddos-detector"
        exit 1
    fi
    
    case $service in
        kafka|zookeeper)
            docker-compose -f "$COMPOSE_DATA_PIPELINE" logs -f --tail="$lines" "$service"
            ;;
        cicflowmeter|flow-processor|ddos-detector)
            docker-compose -f "$COMPOSE_NETWORK" logs -f --tail="$lines" "$service"
            ;;
        prometheus|grafana|cadvisor|node-exporter)
            docker-compose -f "$COMPOSE_MONITORING" logs -f --tail="$lines" "$service"
            ;;
        nginx)
            docker-compose -f "$COMPOSE_NGINX" logs -f --tail="$lines" "$service"
            ;;
        prometheus-kafka-adapter|metrics-flattener)
            docker-compose -f "$COMPOSE_PROM_METRIC" logs -f --tail="$lines" "$service"
            ;;
        *)
            docker logs -f --tail="$lines" "$service"
            ;;
    esac
}

show_urls() {
    print_header "TRUY CẬP CÁC DỊCH VỤ"
    
    echo -e "${GREEN}📊 Monitoring:${NC}"
    echo "  • Prometheus:  http://localhost:9090"
    echo "  • Grafana:     http://localhost:3000  (admin/admin)"
    echo "  • cAdvisor:    http://localhost:8081"
    echo "  • Node Exporter: http://localhost:9100/metrics"
    echo ""
    echo -e "${GREEN}🔍 Detection:${NC}"
    echo "  • DDoS Detector Metrics: http://localhost:8001/metrics"
    echo ""
    echo -e "${GREEN}🌐 Web:${NC}"
    echo "  • Nginx:       http://localhost:8080"
    echo ""
    echo -e "${GREEN}💡 Useful Commands:${NC}"
    echo "  • View DDoS alerts:  docker exec ids_kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic ddos-alerts"
    echo "  • View network flows: docker exec ids_kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic network-flows"
    echo "  • Kafka topics:      docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list"
}

###############################################################################
# Health Check Functions
###############################################################################

health_check() {
    print_header "KIỂM TRA SỨC KHỎE HỆ THỐNG"
    
    local all_healthy=true
    
    # Check Prometheus
    echo -n "Prometheus: "
    if curl -sf http://localhost:9090/-/healthy > /dev/null 2>&1; then
        print_success "OK"
    else
        print_error "FAILED"
        all_healthy=false
    fi
    
    # Check Grafana
    echo -n "Grafana: "
    if curl -sf http://localhost:3000/api/health > /dev/null 2>&1; then
        print_success "OK"
    else
        print_error "FAILED"
        all_healthy=false
    fi
    
    # Check DDoS Detector
    echo -n "DDoS Detector: "
    if curl -sf http://localhost:8001/metrics > /dev/null 2>&1; then
        print_success "OK"
    else
        print_error "FAILED"
        all_healthy=false
    fi
    
    # Check Nginx
    echo -n "Nginx: "
    if curl -sf http://localhost:8080 > /dev/null 2>&1; then
        print_success "OK"
    else
        print_error "FAILED"
        all_healthy=false
    fi
    
    # Check containers
    echo ""
    echo -e "${BLUE}Container Health:${NC}"
    local expected_containers=("ids_zookeeper" "ids_kafka" "ids_ddos_detector" "ids_flow_processor" "prometheus" "grafana" "cadvisor" "node-exporter" "nginx")
    
    for container in "${expected_containers[@]}"; do
        echo -n "$container: "
        if docker ps --filter "name=$container" --filter "status=running" | grep -q "$container"; then
            print_success "Running"
        else
            print_error "Not Running"
            all_healthy=false
        fi
    done
    
    echo ""
    if [ "$all_healthy" = true ]; then
        print_success "Tất cả services đều khỏe mạnh"
    else
        print_error "Một số services có vấn đề"
    fi
}

###############################################################################
# Utility Functions
###############################################################################

update_prometheus_config() {
    print_header "CẬP NHẬT PROMETHEUS CONFIG"
    
    print_info "Đang thêm DDoS Detector vào scrape targets..."
    
    # Reload Prometheus config
    docker exec prometheus sh -c "kill -HUP 1" 2>/dev/null || \
    curl -X POST http://localhost:9090/-/reload
    
    print_success "Đã reload Prometheus config"
}

show_help() {
    cat << EOF
${BLUE}═══════════════════════════════════════════════════════════════════${NC}
${GREEN}Network Monitor System Control Script${NC}
${BLUE}═══════════════════════════════════════════════════════════════════${NC}

${YELLOW}Usage:${NC}
  $0 [command] [options]

${YELLOW}Commands:${NC}
  ${GREEN}start${NC}              Khởi động toàn bộ hệ thống
  ${GREEN}stop${NC}               Dừng toàn bộ hệ thống
  ${GREEN}restart${NC}            Khởi động lại toàn bộ hệ thống
  ${GREEN}restart [service]${NC}  Khởi động lại một service cụ thể
  ${GREEN}status${NC}             Hiển thị trạng thái hệ thống
  ${GREEN}health${NC}             Kiểm tra sức khỏe các services
  ${GREEN}logs [service]${NC}     Xem logs của service
  ${GREEN}urls${NC}               Hiển thị các URL truy cập
  ${GREEN}clean${NC}              Dừng và xóa toàn bộ (bao gồm volumes)
  ${GREEN}update-config${NC}      Cập nhật Prometheus config
  ${GREEN}help${NC}               Hiển thị help

${YELLOW}Services:${NC}
  - data-pipeline   (Kafka, Zookeeper)
  - network         (CICFlowMeter, Flow Processor, DDoS Detector)
  - monitoring      (Prometheus, Grafana, cAdvisor, Node Exporter)
  - nginx           (Web Server)
  - metrics         (Prometheus-Kafka Adapter, Metrics Flattener)

${YELLOW}Examples:${NC}
  $0 start                    # Khởi động toàn bộ
  $0 restart network          # Khởi động lại network detection
  $0 logs ddos-detector       # Xem logs DDoS Detector
  $0 health                   # Kiểm tra sức khỏe
  $0 status                   # Xem trạng thái

${BLUE}═══════════════════════════════════════════════════════════════════${NC}
EOF
}

###############################################################################
# Main
###############################################################################

main() {
    case "${1:-help}" in
        start)
            start_all
            ;;
        stop)
            stop_all
            ;;
        restart)
            if [ -n "$2" ]; then
                restart_service "$2"
            else
                restart_all
            fi
            ;;
        status)
            show_status
            ;;
        health|healthcheck)
            health_check
            ;;
        logs)
            show_logs "$2" "$3"
            ;;
        urls)
            show_urls
            ;;
        clean|remove)
            stop_all_remove
            ;;
        update-config)
            update_prometheus_config
            ;;
        help|-h|--help)
            show_help
            ;;
        *)
            print_error "Command không hợp lệ: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
