#!/bin/bash

# Script kiểm tra cấu hình hệ thống
# Sử dụng: ./verify_config.sh

echo "=========================================="
echo "KIỂM TRA CẤU HÌNH HỆ THỐNG"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Kiểm tra Kafka Topics
echo "1. KAFKA TOPICS"
echo "----------------------------------------"
docker exec ids_kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Kafka topics OK${NC}"
else
    echo -e "${RED}✗ Kafka không chạy hoặc không có topics${NC}"
fi
echo ""

# 2. Kiểm tra Rule-based Detector config
echo "2. RULE-BASED DETECTOR CONFIG"
echo "----------------------------------------"
RULES_FILE="../src/infra/rule-based-detector/rules.yaml"
if [ -f "$RULES_FILE" ]; then
    RULE_COUNT=$(grep -c "^  - id:" "$RULES_FILE")
    echo -e "${GREEN}✓ Rules file exists${NC}"
    echo "  Total rules: $RULE_COUNT"
    echo "  Per-flow rules: $(grep -A 20 "per_flow_rules:" "$RULES_FILE" | grep -c "id:")"
    echo "  Aggregation rules: $(grep -A 200 "aggregation_rules:" "$RULES_FILE" | grep -c "id:")"
else
    echo -e "${RED}✗ Rules file not found${NC}"
fi
echo ""

# 3. Kiểm tra ML Model files
echo "3. ML DETECTOR MODEL FILES"
echo "----------------------------------------"
MODEL_DIR="../src/models/final_model"
if [ -d "$MODEL_DIR" ]; then
    echo -e "${GREEN}✓ Model directory exists${NC}"
    
    if [ -f "$MODEL_DIR/xgb_calibrated_model_reduced.joblib" ]; then
        SIZE=$(du -h "$MODEL_DIR/xgb_calibrated_model_reduced.joblib" | cut -f1)
        echo -e "  ${GREEN}✓${NC} Model file: $SIZE"
    else
        echo -e "  ${RED}✗${NC} Model file not found"
    fi
    
    if [ -f "$MODEL_DIR/features_reduced.pkl" ]; then
        echo -e "  ${GREEN}✓${NC} Features file exists"
    else
        echo -e "  ${RED}✗${NC} Features file not found"
    fi
    
    if [ -f "$MODEL_DIR/threshold_reduced.json" ]; then
        THRESHOLD=$(cat "$MODEL_DIR/threshold_reduced.json" | grep -o '"threshold": [0-9.]*' | cut -d' ' -f2)
        echo -e "  ${GREEN}✓${NC} Threshold file: $THRESHOLD"
    else
        echo -e "  ${RED}✗${NC} Threshold file not found"
    fi
else
    echo -e "${RED}✗ Model directory not found${NC}"
fi
echo ""

# 4. Kiểm tra Prometheus config
echo "4. PROMETHEUS CONFIG"
echo "----------------------------------------"
PROM_CONFIG="../src/configs/prometheus/prometheus.yml"
if [ -f "$PROM_CONFIG" ]; then
    echo -e "${GREEN}✓ Prometheus config exists${NC}"
    SCRAPE_INTERVAL=$(grep "scrape_interval:" "$PROM_CONFIG" | head -1 | awk '{print $2}')
    echo "  Scrape interval: $SCRAPE_INTERVAL"
    JOB_COUNT=$(grep -c "job_name:" "$PROM_CONFIG")
    echo "  Jobs configured: $JOB_COUNT"
else
    echo -e "${RED}✗ Prometheus config not found${NC}"
fi
echo ""

# 5. Kiểm tra Grafana dashboards
echo "5. GRAFANA DASHBOARDS"
echo "----------------------------------------"
DASHBOARD_DIR="../src/configs/grafana/dashboards"
if [ -d "$DASHBOARD_DIR" ]; then
    DASHBOARD_COUNT=$(ls -1 "$DASHBOARD_DIR"/*.json 2>/dev/null | wc -l)
    echo -e "${GREEN}✓ Dashboard directory exists${NC}"
    echo "  Dashboards: $DASHBOARD_COUNT"
    ls -1 "$DASHBOARD_DIR"/*.json 2>/dev/null | xargs -n1 basename
else
    echo -e "${RED}✗ Dashboard directory not found${NC}"
fi
echo ""

# 6. Kiểm tra Telegram config
echo "6. TELEGRAM NOTIFIER CONFIG"
echo "----------------------------------------"
if [ -f "../src/.env" ]; then
    if grep -q "TELEGRAM_BOT_TOKEN" "../src/.env"; then
        TOKEN_SET=$(grep "TELEGRAM_BOT_TOKEN" "../src/.env" | grep -v "^#" | cut -d'=' -f2)
        if [ -n "$TOKEN_SET" ]; then
            echo -e "  ${GREEN}✓${NC} Bot token configured"
        else
            echo -e "  ${YELLOW}⚠${NC} Bot token empty"
        fi
    else
        echo -e "  ${RED}✗${NC} Bot token not found"
    fi
    
    if grep -q "TELEGRAM_CHAT_ID" "../src/.env"; then
        CHAT_SET=$(grep "TELEGRAM_CHAT_ID" "../src/.env" | grep -v "^#" | cut -d'=' -f2)
        if [ -n "$CHAT_SET" ]; then
            echo -e "  ${GREEN}✓${NC} Chat ID configured"
        else
            echo -e "  ${YELLOW}⚠${NC} Chat ID empty"
        fi
    else
        echo -e "  ${RED}✗${NC} Chat ID not found"
    fi
else
    echo -e "${RED}✗ .env file not found${NC}"
fi
echo ""

# 7. Kiểm tra Docker containers
echo "7. DOCKER CONTAINERS STATUS"
echo "----------------------------------------"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep "ids_\|prometheus\|grafana\|telegram" || echo -e "${YELLOW}No containers running${NC}"
echo ""

echo "=========================================="
echo "VERIFICATION COMPLETE"
echo "=========================================="
