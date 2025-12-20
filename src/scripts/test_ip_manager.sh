#!/bin/bash

# Test IP Manager API

API_URL="http://localhost:8002"

echo "=== Testing IP Manager API ==="
echo

echo "1. Get detected IPs:"
curl -s "$API_URL/api/detected-ips" | python3 -m json.tool
echo

echo "2. Manually add a test IP:"
curl -s -X POST "$API_URL/api/detected-ips" \
  -H "Content-Type: application/json" \
  -d '{
    "ip": "192.168.1.100",
    "reason": "Test - Manual detection",
    "severity": "high",
    "flow_count": 1000,
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }' | python3 -m json.tool
echo

echo "3. List detected IPs again:"
curl -s "$API_URL/api/detected-ips" | python3 -m json.tool
echo

echo "4. Get specific IP details:"
curl -s "$API_URL/api/detected-ips/192.168.1.100" | python3 -m json.tool
echo

echo "5. Approve blocking IP:"
curl -s -X POST "$API_URL/api/detected-ips/192.168.1.100/approve" | python3 -m json.tool
echo

echo "6. Check blocked IPs:"
curl -s "$API_URL/api/blocked-ips" | python3 -m json.tool
echo

echo "7. Test metrics endpoint:"
curl -s "$API_URL/metrics" | grep -E "detected_ips|blocked_ips|approve" | head -10
echo

echo "=== Test completed ==="
