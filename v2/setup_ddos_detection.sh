#!/bin/bash
# Quick Setup Script cho DDoS Detection System

set -e

echo "🚀 Setting up DDoS Detection System..."

# 1. Check if models exist
echo ""
echo "📊 Step 1: Checking ML models..."
MODEL_DIR="./models/ddos_detector"

if [ ! -f "$MODEL_DIR/rf_ddos_model.pkl" ]; then
    echo "❌ Models not found!"
    echo ""
    echo "Please train the model first:"
    echo "  1. Open: v2/src/models/ddos_detector/export_random_forest_model.ipynb"
    echo "  2. Run all cells"
    echo "  3. Run: python v2/src/models/ddos_detector/export_models.py"
    exit 1
fi

echo "✅ Models found!"

# 2. Create network if not exists
echo ""
echo "🔧 Step 2: Setting up Docker network..."
docker network create ids-network 2>/dev/null || echo "   Network already exists"

# 3. Build and start services
echo ""
echo "🐳 Step 3: Building and starting services..."
cd src

# Start data pipeline first (Kafka, etc.)
echo "   Starting data pipeline..."
docker-compose -f docker-compose.data-pipeline.yml up -d

# Wait for Kafka
echo "   Waiting for Kafka to be ready..."
sleep 10

# Start network capture and detection
echo "   Starting network capture and detection..."
docker-compose -f docker-compose.network.yml up -d --build

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Check status:"
echo "  docker-compose -f docker-compose.network.yml ps"
echo ""
echo "📝 View logs:"
echo "  docker-compose -f docker-compose.network.yml logs -f ddos-detector"
echo ""
echo "🔍 Monitor alerts:"
echo "  kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic ddos-alerts --from-beginning"
echo ""
echo "📈 Prometheus metrics:"
echo "  curl http://localhost:8000/metrics"
echo ""
