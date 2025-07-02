#!/bin/bash
# Test advice functionality end-to-end

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🧪 Testing advice functionality end-to-end..."

# Check if the advice endpoint is working without authentication
echo "📋 1. Testing advice health endpoint:"
curl -s https://mydscvr.xyz/api/advice/health | head -c 200
echo ""

# Test without authentication (should return 401 or 403)
echo "📋 2. Testing advice creation without auth (should return 401):"
curl -s -X POST https://mydscvr.xyz/api/advice/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "60f1b2e5c8d4e5001f123456",
    "title": "Test Advice",
    "content": "This is a test advice",
    "category": "general",
    "advice_type": "local_knowledge"
  }' | head -c 200
echo ""

# Check recent logs for any errors
echo "📋 3. Checking recent backend logs for errors:"
sudo journalctl -u mydscvr-backend --since "2 minutes ago" | grep -E "(ERROR|CRITICAL|500)" | tail -5
echo ""

# Check if the service is running properly
echo "📋 4. Backend service status:"
sudo systemctl is-active mydscvr-backend
echo ""

# Test frontend connectivity (check if frontend can reach backend)
echo "📋 5. Testing frontend to backend connectivity:"
curl -s https://mydscvr.xyz/api/events/health | head -c 100
echo ""

echo "✅ End-to-end test completed"
echo "🎯 Next steps:"
echo "1. Open the frontend at https://mydscvr.xyz"
echo "2. Navigate to an event details page"
echo "3. Click on the Advice tab"
echo "4. Try to submit advice (should work without 500 errors)"
EOF