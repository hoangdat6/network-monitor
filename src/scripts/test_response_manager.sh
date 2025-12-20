#!/bin/bash

# Test script để simulate DDoS attack và test Response Manager

API_URL="http://localhost:5000"

echo "=== DDoS Response Manager Test ==="
echo

echo "1. Check health:"
curl -s "$API_URL/health" | python3 -m json.tool
echo

echo "2. Get pending IPs (should be empty initially):"
curl -s "$API_URL/ips/pending" | python3 -m json.tool
echo

echo "3. Simulate adding test IPs to Redis manually:"
docker exec ids_redis redis-cli SADD ddos:pending_ips "192.168.1.100" "10.0.0.50"
docker exec ids_redis redis-cli HSET ddos:ip:192.168.1.100 \
  ip "192.168.1.100" \
  severity "high" \
  attack_type "syn_flood" \
  flow_count "5000" \
  confidence "0.95" \
  first_seen "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  last_seen "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  block_status "pending" \
  block_duration "3600" \
  alert_count "3"

docker exec ids_redis redis-cli HSET ddos:ip:10.0.0.50 \
  ip "10.0.0.50" \
  severity "critical" \
  attack_type "http_flood" \
  flow_count "10000" \
  confidence "0.98" \
  first_seen "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  last_seen "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  block_status "pending" \
  block_duration "7200" \
  alert_count "5"
echo

echo "4. Get pending IPs again:"
curl -s "$API_URL/ips/pending" | python3 -m json.tool
echo

echo "5. Approve blocking 192.168.1.100:"
curl -s -X POST "$API_URL/ips/192.168.1.100/approve" \
  -H "Content-Type: application/json" \
  -d '{"duration": 3600}' | python3 -m json.tool
echo

echo "6. Get blocked IPs:"
curl -s "$API_URL/ips/blocked" | python3 -m json.tool
echo

echo "7. Whitelist (reject) 10.0.0.50:"
curl -s -X POST "$API_URL/ips/10.0.0.50/reject" | python3 -m json.tool
echo

echo "8. Final state - Pending IPs:"
curl -s "$API_URL/ips/pending" | python3 -m json.tool
echo

echo "9. Redis stats:"
echo "Pending: $(docker exec ids_redis redis-cli SCARD ddos:pending_ips)"
echo "Blocked: $(docker exec ids_redis redis-cli SCARD ddos:blocked_ips)"
echo "Whitelist: $(docker exec ids_redis redis-cli SCARD ddos:whitelist_ips)"
echo

echo "=== Test completed ==="
