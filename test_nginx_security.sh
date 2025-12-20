#!/bin/bash
# test_nginx_security.sh - Comprehensive Security Testing Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NGINX_URL="${NGINX_URL:-http://localhost:8080}"
NGINX_IP="${NGINX_IP:-localhost}"

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  NGINX Security Layers Testing Suite${NC}"
echo -e "${BLUE}  Target: $NGINX_URL${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"

# ============================================================
# TEST 1: Anti-DDoS Challenge (Lua Script)
# ============================================================
test_lua_challenge() {
    echo -e "\n${YELLOW}[TEST 1] Testing Lua Anti-DDoS Challenge${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}1.1 Testing with curl (should fail - no JS engine)${NC}"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$NGINX_URL/")
    if [ "$RESPONSE" == "200" ]; then
        echo -e "${RED}✗ FAILED: Curl got through (expected challenge page)${NC}"
    else
        echo -e "${GREEN}✓ PASS: Got response code $RESPONSE${NC}"
    fi
    
    echo -e "\n${BLUE}1.2 Testing with real browser (manual)${NC}"
    echo "Open browser and visit: $NGINX_URL"
    echo "Expected: JavaScript challenge page → redirect to site after 5s"
    read -p "Press Enter when done..."
    
    echo -e "\n${BLUE}1.3 Testing bot User-Agent detection${NC}"
    for UA in "curl/7.68" "python-requests/2.25" "Wget/1.20" "bot" "crawler"; do
        RESPONSE=$(curl -s -A "$UA" -o /dev/null -w "%{http_code}" "$NGINX_URL/")
        echo "  User-Agent: $UA → HTTP $RESPONSE"
    done
}

# ============================================================
# TEST 2: Rate Limiting (ddos.conf)
# ============================================================
test_rate_limiting() {
    echo -e "\n${YELLOW}[TEST 2] Testing Rate Limiting${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}2.1 Testing global rate limit (50 req/s)${NC}"
    echo "Sending 100 requests rapidly..."
    
    SUCCESS=0
    RATE_LIMITED=0
    TIMEOUT=0
    
    for i in {1..100}; do
        # Show progress every 10 requests
        if [ $((i % 10)) -eq 0 ]; then
            echo -n "."
        fi
        
        RESPONSE=$(curl -s -m 2 -o /dev/null -w "%{http_code}" "$NGINX_URL/" 2>/dev/null || echo "TIMEOUT")
        
        if [ "$RESPONSE" == "200" ]; then
            ((SUCCESS++))
        elif [ "$RESPONSE" == "429" ] || [ "$RESPONSE" == "503" ]; then
            ((RATE_LIMITED++))
        elif [ "$RESPONSE" == "TIMEOUT" ]; then
            ((TIMEOUT++))
        fi
    done
    echo ""  # New line after progress dots
    
    echo -e "  ${GREEN}✓ Success (200): $SUCCESS requests${NC}"
    echo -e "  ${RED}✗ Rate limited (429/503): $RATE_LIMITED requests${NC}"
    echo -e "  ${YELLOW}⚠ Timeout: $TIMEOUT requests${NC}"
    
    if [ $RATE_LIMITED -gt 0 ]; then
        echo -e "${GREEN}✓ PASS: Rate limiting is working!${NC}"
    elif [ $TIMEOUT -gt 50 ]; then
        echo -e "${YELLOW}⚠ WARNING: Too many timeouts - check Nginx${NC}"
    else
        echo -e "${RED}✗ FAILED: No rate limiting detected${NC}"
    fi
    
    echo -e "\n${BLUE}2.2 Testing login endpoint rate limit (5 req/s)${NC}"
    SUCCESS=0
    RATE_LIMITED=0
    
    for i in {1..20}; do
        echo -n "."
        RESPONSE=$(curl -s -m 2 -o /dev/null -w "%{http_code}" "$NGINX_URL/login" 2>/dev/null || echo "404")
        if [ "$RESPONSE" == "200" ] || [ "$RESPONSE" == "404" ]; then
            ((SUCCESS++))
        elif [ "$RESPONSE" == "429" ] || [ "$RESPONSE" == "503" ]; then
            ((RATE_LIMITED++))
        fi
    done
    echo ""
    
    echo -e "  ${GREEN}✓ Success: $SUCCESS requests${NC}"
    echo -e "  ${RED}✗ Rate limited: $RATE_LIMITED requests${NC}"
    
    if [ $RATE_LIMITED -gt 0 ]; then
        echo -e "${GREEN}✓ PASS: Login rate limiting is stricter!${NC}"
    else
        echo -e "${YELLOW}⚠ WARNING: Login endpoint may not have stricter limits${NC}"
    fi
}

# ============================================================
# TEST 3: Connection Limiting
# ============================================================
test_connection_limiting() {
    echo -e "\n${YELLOW}[TEST 3] Testing Connection Limiting${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}3.1 Opening 30 concurrent connections${NC}"
    
    # Use ab (Apache Bench) if available
    if command -v ab &> /dev/null; then
        ab -n 100 -c 30 "$NGINX_URL/" 2>&1 | grep -E "(Failed requests|Non-2xx responses)"
        echo -e "${GREEN}✓ Test completed (check for failed/rejected connections)${NC}"
    else
        echo -e "${YELLOW}⚠ Apache Bench (ab) not installed${NC}"
        echo "Install: sudo apt install apache2-utils"
        
        # Fallback: manual parallel curl
        echo "Fallback: Using parallel curl..."
        for i in {1..30}; do
            curl -s -o /dev/null "$NGINX_URL/" &
        done
        wait
        echo -e "${GREEN}✓ Sent 30 parallel requests${NC}"
    fi
}

# ============================================================
# TEST 4: Slowloris Protection
# ============================================================
test_slowloris_protection() {
    echo -e "\n${YELLOW}[TEST 4] Testing Slowloris Protection${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}4.1 Testing slow header attack${NC}"
    echo "Sending incomplete request with 15s delay..."
    
    START=$(date +%s)
    (
        exec 3<>/dev/tcp/$NGINX_IP/80
        echo -e "GET / HTTP/1.1\r\nHost: $NGINX_IP\r\n" >&3
        sleep 15
        echo -e "\r\n" >&3
        cat <&3 &
        PID=$!
        sleep 2
        kill $PID 2>/dev/null
    ) 2>&1 | head -1
    END=$(date +%s)
    DURATION=$((END - START))
    
    if [ $DURATION -lt 12 ]; then
        echo -e "${GREEN}✓ PASS: Connection closed early (${DURATION}s < 12s)${NC}"
        echo "  Nginx timeout settings working!"
    else
        echo -e "${RED}✗ FAILED: Connection stayed open too long (${DURATION}s)${NC}"
    fi
}

# ============================================================
# TEST 5: Dynamic IP Blocking
# ============================================================
test_ip_blocking() {
    echo -e "\n${YELLOW}[TEST 5] Testing Dynamic IP Blocking${NC}"
    echo "─────────────────────────────────────────────"
    
    BLOCKED_IPS_FILE="/home/dathv2004/MountDisk/BKDN/Learning/network-monitor/src/configs/nginx/blocked_ips.conf"
    
    if [ ! -f "$BLOCKED_IPS_FILE" ]; then
        echo -e "${YELLOW}⚠ Creating blocked_ips.conf${NC}"
        touch "$BLOCKED_IPS_FILE"
    fi
    
    echo -e "${BLUE}5.1 Adding test IP to blocklist${NC}"
    TEST_IP="192.168.99.99"
    echo "$TEST_IP 1;" > "$BLOCKED_IPS_FILE"
    
    # Reload nginx
    echo "Reloading Nginx..."
    docker exec network-monitor-nginx-1 nginx -s reload 2>/dev/null || \
        sudo nginx -s reload 2>/dev/null || \
        echo -e "${YELLOW}⚠ Could not reload nginx automatically${NC}"
    
    sleep 2
    
    echo -e "${BLUE}5.2 Testing blocked IP${NC}"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -H "X-Forwarded-For: $TEST_IP" "$NGINX_URL/")
    
    if [ "$RESPONSE" == "403" ]; then
        echo -e "${GREEN}✓ PASS: IP $TEST_IP is blocked (403)${NC}"
    else
        echo -e "${RED}✗ FAILED: IP not blocked (got $RESPONSE)${NC}"
    fi
    
    # Cleanup
    echo "" > "$BLOCKED_IPS_FILE"
    echo -e "${BLUE}5.3 Cleaned up test IP${NC}"
}

# ============================================================
# TEST 6: Request Size Limits
# ============================================================
test_request_limits() {
    echo -e "\n${YELLOW}[TEST 6] Testing Request Size Limits${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}6.1 Testing large body (>10MB)${NC}"
    dd if=/dev/zero bs=1M count=15 2>/dev/null | \
        curl -s -o /dev/null -w "HTTP %{http_code}\n" \
        -X POST -H "Content-Type: application/octet-stream" \
        --data-binary @- "$NGINX_URL/api/upload"
    
    echo -e "${BLUE}6.2 Testing large headers${NC}"
    LARGE_HEADER=$(python3 -c "print('X' * 20000)")
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "X-Large-Header: $LARGE_HEADER" "$NGINX_URL/" 2>/dev/null || echo "400")
    
    if [ "$RESPONSE" == "400" ] || [ "$RESPONSE" == "413" ]; then
        echo -e "${GREEN}✓ PASS: Large headers rejected (HTTP $RESPONSE)${NC}"
    else
        echo -e "${RED}✗ FAILED: Large headers accepted${NC}"
    fi
}

# ============================================================
# TEST 7: ModSecurity (if enabled)
# ============================================================
test_modsecurity() {
    echo -e "\n${YELLOW}[TEST 7] Testing ModSecurity WAF${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}7.1 Testing SQL Injection${NC}"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        "$NGINX_URL/?id=1' OR '1'='1")
    echo "  SQL injection attempt → HTTP $RESPONSE"
    
    echo -e "${BLUE}7.2 Testing XSS${NC}"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        "$NGINX_URL/?search=<script>alert('xss')</script>")
    echo "  XSS attempt → HTTP $RESPONSE"
    
    echo -e "${BLUE}7.3 Testing Path Traversal${NC}"
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        "$NGINX_URL/../../../etc/passwd")
    echo "  Path traversal → HTTP $RESPONSE"
    
    echo -e "\n${YELLOW}Note: If ModSecurity is enabled, attacks should return 403${NC}"
}

# ============================================================
# TEST 8: Monitoring & Logging
# ============================================================
test_logging() {
    echo -e "\n${YELLOW}[TEST 8] Testing Logging & Monitoring${NC}"
    echo "─────────────────────────────────────────────"
    
    echo -e "${BLUE}8.1 Checking log files${NC}"
    
    LOG_DIR="/var/log/nginx"
    DOCKER_LOGS="docker logs network-monitor-nginx-1"
    
    if [ -f "$LOG_DIR/access.ids.log" ]; then
        echo -e "${GREEN}✓ Found: access.ids.log${NC}"
        tail -n 3 "$LOG_DIR/access.ids.log"
    else
        echo -e "${YELLOW}⚠ Using docker logs${NC}"
        $DOCKER_LOGS --tail 5 2>/dev/null || echo "No docker container"
    fi
    
    if [ -f "$LOG_DIR/blocked.log" ]; then
        echo -e "${GREEN}✓ Found: blocked.log${NC}"
        BLOCKED_COUNT=$(wc -l < "$LOG_DIR/blocked.log")
        echo "  Total blocked requests: $BLOCKED_COUNT"
    fi
}

# ============================================================
# MAIN EXECUTION
# ============================================================
main() {
    # Check if nginx is running
    if ! curl -s -o /dev/null "$NGINX_URL"; then
        echo -e "${RED}✗ ERROR: Cannot reach $NGINX_URL${NC}"
        echo "Make sure Nginx is running!"
        exit 1
    fi
    
    # Run all tests
    test_lua_challenge
    test_rate_limiting
    test_connection_limiting
    test_slowloris_protection
    test_ip_blocking
    test_request_limits
    test_modsecurity
    test_logging
    
    echo -e "\n${BLUE}═══════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ All tests completed!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════${NC}\n"
    
    echo -e "${YELLOW}Manual Tests Remaining:${NC}"
    echo "1. Open browser and test JavaScript challenge"
    echo "2. Test from different IPs (if possible)"
    echo "3. Monitor Grafana dashboards during load"
}

# Run specific test or all
if [ $# -eq 0 ]; then
    main
else
    case $1 in
        1|lua) test_lua_challenge ;;
        2|rate) test_rate_limiting ;;
        3|conn) test_connection_limiting ;;
        4|slowloris) test_slowloris_protection ;;
        5|block) test_ip_blocking ;;
        6|limits) test_request_limits ;;
        7|waf) test_modsecurity ;;
        8|log) test_logging ;;
        *) echo "Usage: $0 [1-8|lua|rate|conn|slowloris|block|limits|waf|log]" ;;
    esac
fi