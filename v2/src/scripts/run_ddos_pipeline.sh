#!/bin/bash

# =====================================
# DDoS Detection Pipeline Deployment Script
# =====================================
# Script này khởi động toàn bộ pipeline phát hiện DDoS bao gồm:
# 1. Network Infrastructure (Kafka, Zookeeper)
# 2. Data Pipeline (Flow processing)
# 3. DDoS Detection Service (Random Forest ML)
# 4. Monitoring Stack (Prometheus, Grafana)
# 5. Security Layer (Nginx with Anti-DDoS)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project configuration
PROJECT_NAME="Network Monitor DDoS Detection"
BASE_DIR="/home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/v2/src"
NETWORK_NAME="ids-network"

# Function to print colored messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}"
    echo "========================================"
    echo "$1"
    echo "========================================"
    echo -e "${NC}"
}

# Function to check if Docker is running
check_docker() {
    print_status "Checking Docker status..."
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_success "Docker is running"
}

# Function to check if docker-compose is available
check_docker_compose() {
    print_status "Checking docker-compose availability..."
    if ! command -v docker-compose &> /dev/null; then
        print_error "docker-compose is not installed or not in PATH"
        exit 1
    fi
    print_success "docker-compose is available"
}

# Function to create external network
create_network() {
    print_status "Creating Docker network: $NETWORK_NAME"
    if docker network ls | grep -q "$NETWORK_NAME"; then
        print_warning "Network $NETWORK_NAME already exists"
    else
        docker network create "$NETWORK_NAME"
        print_success "Network $NETWORK_NAME created"
    fi
}

# Function to validate compose files
validate_compose_files() {
    print_status "Validating docker-compose files..."
    
    local compose_files=(
        "docker-compose.data-pipeline.yml"
        "docker-compose.ddos-detection.yml"
        "docker-compose.monitoring.yml"
        "docker-compose.network.yml"
        "docker-compose.nginx.yml"
    )
    
    cd "$BASE_DIR"
    
    for file in "${compose_files[@]}"; do
        if [[ -f "$file" ]]; then
            if docker-compose -f "$file" config >/dev/null 2>&1; then
                print_success "✓ $file is valid"
            else
                print_error "✗ $file has errors"
                docker-compose -f "$file" config
                exit 1
            fi
        else
            print_warning "⚠ $file not found (optional)"
        fi
    done
}

# Function to build custom images
build_images() {
    print_header "Building Custom Docker Images"
    
    cd "$BASE_DIR"
    
    # Build DDoS Detector image
    if [[ -d "detection/ddos-detector" ]]; then
        print_status "Building DDoS Detector image..."
        cd detection/ddos-detector
        
        # Check if models exist
        if [[ ! -d "models" || ! -f "models/random_forest_ddos.pkl" ]]; then
            print_warning "ML models not found. Running model export..."
            python3 model_exporter.py 2>/dev/null || {
                print_error "Failed to export models. Please run model_exporter.py manually"
                exit 1
            }
        fi
        
        docker build -t ddos-detector . || {
            print_error "Failed to build ddos-detector image"
            exit 1
        }
        print_success "DDoS Detector image built successfully"
        cd "$BASE_DIR"
    else
        print_warning "DDoS Detector directory not found"
    fi
    
    # Build other custom images if needed
    if [[ -d "detection/web-attack-detector" ]]; then
        print_status "Building Web Attack Detector image..."
        cd detection/web-attack-detector
        docker build -t web-attack-detector . || {
            print_warning "Failed to build web-attack-detector image"
        }
        cd "$BASE_DIR"
    fi
}

# Function to start data pipeline (Kafka, Zookeeper)
start_data_pipeline() {
    print_header "Starting Data Pipeline (Kafka + Zookeeper)"
    
    cd "$BASE_DIR"
    
    print_status "Starting Kafka and Zookeeper..."
    docker-compose -f docker-compose.data-pipeline.yml up -d
    
    # Wait for Kafka to be ready
    print_status "Waiting for Kafka to be ready..."
    sleep 30
    
    # Verify Kafka is running
    if docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
        print_success "Kafka is ready and accepting connections"
    else
        print_error "Kafka failed to start properly"
        docker-compose -f docker-compose.data-pipeline.yml logs kafka
        exit 1
    fi
}

# Function to start DDoS detection service
start_ddos_detection() {
    print_header "Starting DDoS Detection Service"
    
    cd "$BASE_DIR"
    
    print_status "Starting DDoS Detector with Random Forest..."
    docker-compose -f docker-compose.ddos-detection.yml up -d
    
    # Wait for service to start
    sleep 15
    
    # Check if service is healthy
    if docker ps | grep -q "ddos-detector"; then
        print_success "DDoS Detection service is running"
        
        # Show service logs
        print_status "Recent DDoS Detector logs:"
        docker logs ddos-detector --tail 10
    else
        print_error "DDoS Detection service failed to start"
        docker-compose -f docker-compose.ddos-detection.yml logs ddos-detector
        exit 1
    fi
}

# Function to start monitoring stack
start_monitoring() {
    print_header "Starting Monitoring Stack (Prometheus + Node Exporter + cAdvisor)"
    
    cd "$BASE_DIR"
    
    # Check if monitoring configs exist
    if [[ ! -d "configs/prometheus" ]]; then
        print_warning "Prometheus configs not found. Creating basic configuration..."
        mkdir -p configs/prometheus
        
        # Create basic prometheus.yml
        cat > configs/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"
  - "metrics_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
  
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
  
  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka:9092']
EOF
        
        # Create basic alert rules
        cat > configs/prometheus/alert_rules.yml << 'EOF'
groups:
  - name: ddos_detection
    rules:
      - alert: HighDDoSDetectionRate
        expr: increase(ddos_alerts_total[5m]) > 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High DDoS detection rate"
          description: "More than 10 DDoS alerts in the last 5 minutes"
EOF
        
        # Create basic metrics rules
        touch configs/prometheus/metrics_rules.yml
    fi
    
    print_status "Starting monitoring stack..."
    docker-compose -f docker-compose.monitoring.yml up -d
    
    sleep 20
    
    # Verify Prometheus is accessible
    if curl -s http://localhost:9090/-/ready >/dev/null 2>&1; then
        print_success "Prometheus is ready at http://localhost:9090"
    else
        print_warning "Prometheus may not be fully ready yet"
    fi
    
    print_success "Monitoring stack started successfully"
}

# Function to start network capture (if available)
start_network_capture() {
    print_header "Starting Network Capture Services"
    
    cd "$BASE_DIR"
    
    if [[ -f "docker-compose.network.yml" ]]; then
        print_status "Starting network capture services..."
        docker-compose -f docker-compose.network.yml up -d || {
            print_warning "Failed to start network capture services (may require root privileges)"
        }
    else
        print_warning "Network capture configuration not found"
    fi
}

# Function to start Nginx security layer
start_nginx_security() {
    print_header "Starting Nginx Security Layer"
    
    cd "$BASE_DIR"
    
    if [[ -f "docker-compose.nginx.yml" ]]; then
        print_status "Starting Nginx with anti-DDoS protection..."
        docker-compose -f docker-compose.nginx.yml up -d || {
            print_warning "Failed to start Nginx security layer"
        }
        
        if docker ps | grep -q nginx; then
            print_success "Nginx security layer is running"
        fi
    else
        print_warning "Nginx configuration not found"
    fi
}

# Function to create Kafka topics
setup_kafka_topics() {
    print_header "Setting up Kafka Topics"
    
    local topics=(
        "network-flows"
        "security-alerts" 
        "ddos-alerts"
        "web-attack-alerts"
        "system-metrics"
    )
    
    print_status "Creating Kafka topics..."
    
    for topic in "${topics[@]}"; do
        print_status "Creating topic: $topic"
        docker exec ids_kafka kafka-topics.sh \
            --bootstrap-server localhost:9092 \
            --create \
            --topic "$topic" \
            --partitions 3 \
            --replication-factor 1 \
            --if-not-exists || {
            print_warning "Failed to create topic $topic (may already exist)"
        }
    done
    
    # Verify topics
    print_status "Verifying created topics:"
    docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
}

# Function to show service status
show_status() {
    print_header "Service Status Summary"
    
    echo -e "${BLUE}Running Containers:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(kafka|zookeeper|ddos|prometheus|nginx|cadvisor)" || echo "No matching containers found"
    
    echo -e "\n${BLUE}Network Information:${NC}"
    docker network ls | grep "$NETWORK_NAME" || echo "Network not found"
    
    echo -e "\n${BLUE}Service URLs:${NC}"
    echo "• Prometheus: http://localhost:9090"
    echo "• Node Exporter: http://localhost:9100"
    echo "• cAdvisor: http://localhost:8081"
    echo "• Kafka: localhost:9092"
    
    echo -e "\n${BLUE}Kafka Topics:${NC}"
    docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list 2>/dev/null || echo "Kafka not accessible"
    
    echo -e "\n${BLUE}Recent DDoS Detector Logs:${NC}"
    docker logs ddos-detector --tail 5 2>/dev/null || echo "DDoS Detector not running"
}

# Function to test the pipeline
test_pipeline() {
    print_header "Testing DDoS Detection Pipeline"
    
    print_status "Testing Kafka connectivity..."
    if docker exec ids_kafka kafka-console-producer.sh --bootstrap-server localhost:9092 --topic network-flows <<< '{"test": "message"}' 2>/dev/null; then
        print_success "Kafka is accepting messages"
    else
        print_error "Kafka connectivity test failed"
    fi
    
    print_status "Testing DDoS detector service..."
    if docker logs ddos-detector 2>/dev/null | grep -q "Starting DDoS Detector"; then
        print_success "DDoS Detector service is operational"
    else
        print_warning "DDoS Detector may not be fully initialized"
    fi
    
    print_status "Pipeline testing completed"
}

# Function to cleanup services
cleanup() {
    print_header "Cleaning Up Services"
    
    cd "$BASE_DIR"
    
    print_status "Stopping all services..."
    
    local compose_files=(
        "docker-compose.nginx.yml"
        "docker-compose.ddos-detection.yml"
        "docker-compose.monitoring.yml"
        "docker-compose.network.yml"
        "docker-compose.data-pipeline.yml"
    )
    
    for file in "${compose_files[@]}"; do
        if [[ -f "$file" ]]; then
            print_status "Stopping services in $file..."
            docker-compose -f "$file" down || true
        fi
    done
    
    print_status "Removing unused containers and images..."
    docker system prune -f
    
    print_success "Cleanup completed"
}

# Function to show help
show_help() {
    echo -e "${BLUE}DDoS Detection Pipeline Management Script${NC}"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     - Start complete DDoS detection pipeline"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart all services"
    echo "  status    - Show service status"
    echo "  test      - Test pipeline functionality"
    echo "  logs      - Show service logs"
    echo "  cleanup   - Clean up stopped containers and images"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start          # Start all services"
    echo "  $0 status         # Check service status"
    echo "  $0 logs ddos      # Show DDoS detector logs"
    echo ""
}

# Function to show logs
show_logs() {
    local service=${2:-"all"}
    
    case $service in
        "ddos"|"ddos-detector")
            docker logs -f ddos-detector
            ;;
        "kafka")
            docker logs -f ids_kafka
            ;;
        "prometheus")
            docker logs -f prometheus
            ;;
        "all"|*)
            print_status "Showing logs for all services..."
            docker-compose -f "$BASE_DIR/docker-compose.data-pipeline.yml" logs --tail=20
            docker-compose -f "$BASE_DIR/docker-compose.ddos-detection.yml" logs --tail=20
            docker-compose -f "$BASE_DIR/docker-compose.monitoring.yml" logs --tail=20
            ;;
    esac
}

# Main execution logic
main() {
    print_header "$PROJECT_NAME - Deployment Script"
    
    case ${1:-"help"} in
        "start")
            check_docker
            check_docker_compose
            create_network
            validate_compose_files
            build_images
            start_data_pipeline
            setup_kafka_topics
            start_ddos_detection
            start_monitoring
            start_network_capture
            start_nginx_security
            show_status
            test_pipeline
            print_success "🎉 DDoS Detection Pipeline started successfully!"
            print_status "Access Prometheus at: http://localhost:9090"
            print_status "Monitor container stats at: http://localhost:8081"
            ;;
        "stop")
            cleanup
            ;;
        "restart")
            cleanup
            sleep 5
            main start
            ;;
        "status")
            show_status
            ;;
        "test")
            test_pipeline
            ;;
        "logs")
            show_logs "$@"
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Run main function with all arguments
main "$@"