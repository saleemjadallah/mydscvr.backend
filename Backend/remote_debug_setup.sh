#!/bin/bash
# Remote script to add debug endpoint for advice 500 error investigation

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🔧 Setting up debug tools for advice 500 error..."

cd /home/ubuntu/mydscvr-backend/Backend

# Run the debug endpoint addition script
echo "📝 Adding debug endpoint..."
source ../venv/bin/activate
python add_advice_debug_endpoint.py

# Restart the backend service
echo "🔄 Restarting backend service..."
sudo systemctl restart mydscvr-backend

# Wait for service to start
sleep 5

# Check service status
echo "📊 Checking service status..."
sudo systemctl status mydscvr-backend --no-pager -l

# Test the debug endpoint
echo "🧪 Testing debug endpoint..."
curl -s https://mydscvr.xyz/api/advice/debug \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"test": "debug"}' || echo "Debug endpoint test failed (expected - needs auth)"

echo "✅ Debug setup completed"
EOF