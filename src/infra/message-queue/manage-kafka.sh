#!/bin/bash

# =============================================================================
# Kafka Cluster Management Script
# 
# Mục đích: Quản lý Kafka cluster và các services liên quan
# Tại sao script: Simplified operations, health checks, troubleshooting
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check if docker-compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
            error "Docker Compose not found. Please install Docker Compose."
        else
            # Use docker compose (newer syntax)
            DOCKER_COMPOSE_CMD="docker compose"
        fi
    else
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
}

# Start Kafka cluster
start_cluster() {
    log "Starting Kafka cluster..."
    
    # Check if containers are already running
    if $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps | grep -q "Up"; then
        warn "Some containers are already running. Stopping them first..."
        stop_cluster
        sleep 5
    fi
    
    # Start services in order
    log "Starting Zookeeper..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d zookeeper
    
    # Wait for Zookeeper to be ready
    wait_for_service "zookeeper" 2181 30
    
    log "Starting Kafka..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d kafka
    
    # Wait for Kafka to be ready
    wait_for_service "kafka" 9092 60
    
    log "Starting Schema Registry..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d schema-registry
    
    log "Starting Kafka Connect..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d kafka-connect
    
    log "Starting Kafka UI..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d kafka-ui
    
    log "Starting Fluent Bit..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up -d fluent-bit
    
    log "Initializing topics..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" up kafka-init
    
    log "Kafka cluster started successfully!"
    log "Access Kafka UI at: http://localhost:8080"
    log "Kafka brokers available at: localhost:9092"
    log "Schema Registry available at: http://localhost:8081"
}

# Stop Kafka cluster
stop_cluster() {
    log "Stopping Kafka cluster..."
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" down
    log "Kafka cluster stopped."
}

# Restart Kafka cluster
restart_cluster() {
    log "Restarting Kafka cluster..."
    stop_cluster
    sleep 5
    start_cluster
}

# Wait for service to be ready
wait_for_service() {
    local service_name=$1
    local port=$2
    local timeout=${3:-30}
    local counter=0
    
    info "Waiting for $service_name to be ready on port $port..."
    
    while [ $counter -lt $timeout ]; do
        if docker exec network-monitor-$service_name nc -z localhost $port 2>/dev/null; then
            log "$service_name is ready!"
            return 0
        fi
        sleep 2
        counter=$((counter + 2))
        echo -n "."
    done
    
    error "$service_name failed to start within $timeout seconds"
}

# Check cluster health
health_check() {
    log "Checking Kafka cluster health..."
    
    # Check if containers are running
    local running_containers=$($DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps --services --filter "status=running")
    local total_containers=$($DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps --services)
    
    echo "Container Status:"
    echo "================"
    $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps
    echo ""
    
    # Check Kafka broker
    if docker exec network-monitor-kafka kafka-broker-api-versions --bootstrap-server localhost:9092 &>/dev/null; then
        log "✅ Kafka broker is healthy"
    else
        error "❌ Kafka broker is not responding"
    fi
    
    # Check topics
    log "Kafka topics:"
    docker exec network-monitor-kafka kafka-topics --list --bootstrap-server localhost:9092
    
    # Check Schema Registry
    if curl -s http://localhost:8081/subjects &>/dev/null; then
        log "✅ Schema Registry is healthy"
    else
        warn "❌ Schema Registry is not responding"
    fi
    
    # Check Kafka UI
    if curl -s http://localhost:8080 &>/dev/null; then
        log "✅ Kafka UI is accessible"
    else
        warn "❌ Kafka UI is not accessible"
    fi
    
    # Check Fluent Bit
    if curl -s http://localhost:2020 &>/dev/null; then
        log "✅ Fluent Bit is healthy"
    else
        warn "❌ Fluent Bit is not responding"
    fi
}

# View logs
view_logs() {
    local service=${1:-""}
    
    if [ -z "$service" ]; then
        log "Viewing all logs..."
        $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" logs -f
    else
        log "Viewing logs for $service..."
        $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" logs -f "$service"
    fi
}

# Create topic
create_topic() {
    local topic_name=$1
    local partitions=${2:-3}
    local replication=${3:-1}
    
    if [ -z "$topic_name" ]; then
        error "Topic name is required"
    fi
    
    log "Creating topic: $topic_name (partitions: $partitions, replication: $replication)"
    
    docker exec network-monitor-kafka kafka-topics \
        --create \
        --bootstrap-server localhost:9092 \
        --topic "$topic_name" \
        --partitions "$partitions" \
        --replication-factor "$replication" \
        --if-not-exists
        
    log "Topic $topic_name created successfully"
}

# List topics
list_topics() {
    log "Listing Kafka topics..."
    docker exec network-monitor-kafka kafka-topics --list --bootstrap-server localhost:9092
}

# Describe topic
describe_topic() {
    local topic_name=$1
    
    if [ -z "$topic_name" ]; then
        error "Topic name is required"
    fi
    
    log "Describing topic: $topic_name"
    docker exec network-monitor-kafka kafka-topics \
        --describe \
        --bootstrap-server localhost:9092 \
        --topic "$topic_name"
}

# Delete topic
delete_topic() {
    local topic_name=$1
    
    if [ -z "$topic_name" ]; then
        error "Topic name is required"
    fi
    
    warn "Deleting topic: $topic_name"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker exec network-monitor-kafka kafka-topics \
            --delete \
            --bootstrap-server localhost:9092 \
            --topic "$topic_name"
        log "Topic $topic_name deleted"
    else
        log "Operation cancelled"
    fi
}

# Produce test message
test_produce() {
    local topic=${1:-"test-topic"}
    local message=${2:-"Hello from Kafka!"}
    
    log "Producing test message to topic: $topic"
    echo "$message" | docker exec -i network-monitor-kafka kafka-console-producer \
        --bootstrap-server localhost:9092 \
        --topic "$topic"
    log "Message sent successfully"
}

# Consume messages
test_consume() {
    local topic=${1:-"test-topic"}
    
    log "Consuming messages from topic: $topic (Press Ctrl+C to stop)"
    docker exec -it network-monitor-kafka kafka-console-consumer \
        --bootstrap-server localhost:9092 \
        --topic "$topic" \
        --from-beginning
}

# Monitor cluster performance
monitor() {
    log "Starting Kafka cluster monitoring..."
    
    while true; do
        clear
        echo "===================="
        echo "Kafka Cluster Monitor"
        echo "===================="
        echo "Time: $(date)"
        echo ""
        
        # Container status
        echo "Container Status:"
        $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" ps
        echo ""
        
        # Topic list
        echo "Topics:"
        docker exec network-monitor-kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null || echo "Error listing topics"
        echo ""
        
        # Consumer groups
        echo "Consumer Groups:"
        docker exec network-monitor-kafka kafka-consumer-groups --list --bootstrap-server localhost:9092 2>/dev/null || echo "No consumer groups"
        echo ""
        
        sleep 10
    done
}

# Clean up (remove all data)
cleanup() {
    warn "This will remove ALL Kafka data and containers!"
    read -p "Are you sure? (y/N) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Stopping cluster..."
        $DOCKER_COMPOSE_CMD -f "$DOCKER_COMPOSE_FILE" down -v --remove-orphans
        
        log "Removing volumes..."
        docker volume ls -q | grep network-monitor | xargs -r docker volume rm
        
        log "Cleanup completed"
    else
        log "Operation cancelled"
    fi
}

# Show usage
usage() {
    echo "Kafka Cluster Management Script"
    echo "=============================="
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start                    Start the Kafka cluster"
    echo "  stop                     Stop the Kafka cluster"
    echo "  restart                  Restart the Kafka cluster"
    echo "  health                   Check cluster health"
    echo "  logs [service]           View logs (all services or specific service)"
    echo "  monitor                  Monitor cluster performance"
    echo ""
    echo "Topic Management:"
    echo "  create-topic <name> [partitions] [replication]  Create a topic"
    echo "  list-topics              List all topics"
    echo "  describe-topic <name>    Describe a topic"
    echo "  delete-topic <name>      Delete a topic"
    echo ""
    echo "Testing:"
    echo "  test-produce [topic] [message]   Send test message"
    echo "  test-consume [topic]             Consume messages"
    echo ""
    echo "Maintenance:"
    echo "  cleanup                  Remove all data and containers"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 create-topic my-topic 6 1"
    echo "  $0 test-produce my-topic 'Hello World'"
    echo "  $0 logs kafka"
}

# Main script
main() {
    check_docker_compose
    
    case "${1:-}" in
        "start")
            start_cluster
            ;;
        "stop")
            stop_cluster
            ;;
        "restart")
            restart_cluster
            ;;
        "health")
            health_check
            ;;
        "logs")
            view_logs "$2"
            ;;
        "monitor")
            monitor
            ;;
        "create-topic")
            create_topic "$2" "$3" "$4"
            ;;
        "list-topics")
            list_topics
            ;;
        "describe-topic")
            describe_topic "$2"
            ;;
        "delete-topic")
            delete_topic "$2"
            ;;
        "test-produce")
            test_produce "$2" "$3"
            ;;
        "test-consume")
            test_consume "$2"
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"-h"|"--help")
            usage
            ;;
        *)
            error "Unknown command: ${1:-}"
            echo ""
            usage
            ;;
    esac
}

# Run main function
main "$@"