#!/bin/bash

# =====================================
# Quick DDoS Pipeline Launcher
# =====================================
# Simple script to start/stop the complete DDoS detection pipeline

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_DIR="/home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/v2/src"
COMPOSE_FILE="docker-compose.ddos-pipeline.yml"

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Change to project directory
cd "$BASE_DIR"

case "${1:-help}" in
    "start"|"up")
        print_status "🚀 Starting DDoS Detection Pipeline..."
        
        # Create network if needed
        docker network create ids-network 2>/dev/null || print_warning "Network already exists"
        
        # Start services
        docker-compose -f "$COMPOSE_FILE" up -d
        
        print_status "⏳ Waiting for services to be ready..."
        sleep 30
        
        # Create Kafka topics
        print_status "📝 Creating Kafka topics..."
        docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic network-flows --partitions 3 --replication-factor 1 --if-not-exists
        docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic security-alerts --partitions 3 --replication-factor 1 --if-not-exists
        docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --create --topic ddos-alerts --partitions 3 --replication-factor 1 --if-not-exists
        
        print_success "✅ DDoS Detection Pipeline is running!"
        echo ""
        echo "🌐 Access Points:"
        echo "  • Prometheus: http://localhost:9090"
        echo "  • Kafka UI: http://localhost:8080"
        echo "  • cAdvisor: http://localhost:8081"
        echo "  • Node Exporter: http://localhost:9100"
        echo ""
        echo "📊 View logs: $0 logs"
        echo "🔄 Stop services: $0 stop"
        ;;
        
    "stop"|"down")
        print_status "🛑 Stopping DDoS Detection Pipeline..."
        docker-compose -f "$COMPOSE_FILE" down
        print_success "✅ All services stopped"
        ;;
        
    "restart")
        print_status "🔄 Restarting DDoS Detection Pipeline..." 
        docker-compose -f "$COMPOSE_FILE" down
        sleep 5
        docker-compose -f "$COMPOSE_FILE" up -d
        print_success "✅ Pipeline restarted"
        ;;
        
    "status"|"ps")
        print_status "📋 Service Status:"
        docker-compose -f "$COMPOSE_FILE" ps
        echo ""
        print_status "🔗 Running Containers:"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(kafka|zookeeper|ddos|prometheus|cadvisor|kafka-ui)"
        ;;
        
    "logs")
        service=${2:-"ddos-detector"}
        print_status "📜 Showing logs for: $service"
        docker logs -f "$service" 2>/dev/null || docker-compose -f "$COMPOSE_FILE" logs -f "$service"
        ;;
        
    "test")
        print_status "🧪 Testing pipeline..."
        
        # Test Kafka
        echo '{"test_flow": {"src_ip": "192.168.1.100", "dst_ip": "10.0.0.1", "packets": 100}}' | \
        docker exec -i ids_kafka kafka-console-producer.sh --bootstrap-server localhost:9092 --topic network-flows
        
        print_success "✅ Test message sent to Kafka"
        
        # Show recent DDoS detector logs
        print_status "📜 Recent DDoS Detector activity:"
        docker logs ddos-detector --tail 10
        ;;
        
    "topics")
        print_status "📝 Kafka Topics:"
        docker exec ids_kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
        ;;
        
    "build")
        print_status "🔨 Building custom images..."
        cd detection/ddos-detector
        
        # Export models if needed
        if [[ ! -f "models/random_forest_ddos.pkl" ]]; then
            print_status "📊 Exporting ML models..."
            python3 model_exporter.py
        fi
        
        docker build -t ddos-detector .
        print_success "✅ Images built successfully"
        ;;
        
    "clean")
        print_status "🧹 Cleaning up..."
        docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
        docker system prune -f
        print_success "✅ Cleanup completed"
        ;;
        
    "help"|*)
        echo -e "${BLUE}DDoS Detection Pipeline - Quick Launcher${NC}"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  start/up    - Start the complete pipeline"
        echo "  stop/down   - Stop all services"
        echo "  restart     - Restart all services"
        echo "  status/ps   - Show service status"
        echo "  logs [svc]  - Show logs (default: ddos-detector)"
        echo "  test        - Send test message through pipeline"
        echo "  topics      - List Kafka topics"
        echo "  build       - Build custom Docker images"
        echo "  clean       - Stop and clean up everything"
        echo "  help        - Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 start                # Start everything"
        echo "  $0 logs kafka          # Show Kafka logs"
        echo "  $0 test                # Test the pipeline"
        echo ""
        ;;
esac