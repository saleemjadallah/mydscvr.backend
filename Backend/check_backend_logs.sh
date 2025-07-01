#!/bin/bash
# Check backend logs for 500 errors

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🔍 Checking backend logs for 500 errors..."

# Check systemd logs for recent errors
echo "📋 Recent systemd logs (last 20 minutes):"
sudo journalctl -u mydscvr-backend --since "20 minutes ago" --no-pager | tail -20

echo ""
echo "📋 Recent error logs:"
sudo journalctl -u mydscvr-backend --since "20 minutes ago" | grep -i error

echo ""
echo "📋 Recent advice-related logs:"
sudo journalctl -u mydscvr-backend --since "20 minutes ago" | grep -i advice

echo ""
echo "📋 Backend log file (if exists):"
if [ -f "/home/ubuntu/backend/backend.log" ]; then
    tail -20 /home/ubuntu/backend/backend.log
fi

echo ""
echo "📋 Testing a simple advice creation request with debug info:"

# Test with a valid event ID
EVENT_RESPONSE=$(curl -s "https://mydscvr.xyz/api/events?limit=1")
echo "Sample event response: $EVENT_RESPONSE" | head -c 200

echo ""
echo "📋 Testing advice endpoint directly on localhost:"
curl -s -X POST http://localhost:8000/api/advice/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "60f1b2e5c8d4e5001f123456",
    "title": "Test",
    "content": "Test content",
    "category": "general",
    "advice_type": "local_knowledge"
  }' | head -c 200

echo ""
echo "✅ Log check completed"
EOF