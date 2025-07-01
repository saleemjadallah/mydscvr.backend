#!/bin/bash
# Script to trigger the 500 error and monitor logs

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🎯 Triggering 500 error test and monitoring logs..."

# Start log monitoring in background
sudo journalctl -u mydscvr-backend --since "1 minute ago" -f > /tmp/backend_logs.txt 2>&1 &
LOG_PID=$!

# Wait a moment for log monitoring to start
sleep 2

# Get a sample event ID first
echo "📋 Getting sample event ID..."
SAMPLE_EVENT=$(curl -s "https://mydscvr.xyz/api/events?limit=1" | head -c 500)
echo "Sample event response: $SAMPLE_EVENT"

# Try to extract event ID from response
EVENT_ID=$(echo "$SAMPLE_EVENT" | grep -o '"_id":"[^"]*"' | head -1 | cut -d'"' -f4)
echo "Extracted event ID: $EVENT_ID"

# If we couldn't get event ID, use a dummy one
if [ -z "$EVENT_ID" ]; then
    EVENT_ID="60f1b2e5c8d4e5001f123456"
    echo "Using dummy event ID: $EVENT_ID"
fi

# Try various approaches to trigger the 500 error
echo "🔥 Attempting to trigger 500 error..."

# Method 1: Try with a malformed Authorization header
echo "Method 1: Malformed auth header"
curl -s -X POST https://mydscvr.xyz/api/advice/ \
  -H "Authorization: Bearer invalid_token_to_trigger_500" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_id\": \"$EVENT_ID\",
    \"title\": \"Test Advice\",
    \"content\": \"This is a test advice\",
    \"category\": \"general\",
    \"advice_type\": \"local_knowledge\"
  }" | head -c 200

echo ""

# Method 2: Try with a valid-looking but expired token
echo "Method 2: Expired-looking token"
curl -s -X POST https://mydscvr.xyz/api/advice/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_id\": \"$EVENT_ID\",
    \"title\": \"Test Advice\",
    \"content\": \"This is a test advice\",
    \"category\": \"general\",
    \"advice_type\": \"local_knowledge\"
  }" | head -c 200

echo ""

# Method 3: Try with various malformed data
echo "Method 3: Malformed data"
curl -s -X POST https://mydscvr.xyz/api/advice/ \
  -H "Authorization: Bearer malformed_token" \
  -H "Content-Type: application/json" \
  -d "{
    \"event_id\": \"invalid_object_id\",
    \"title\": \"Test Advice\",
    \"content\": \"This is a test advice\",
    \"category\": \"general\",
    \"advice_type\": \"local_knowledge\"
  }" | head -c 200

echo ""

# Wait a moment for logs to be captured
sleep 3

# Stop log monitoring
kill $LOG_PID 2>/dev/null

# Show the captured logs
echo "📋 Captured logs during 500 error attempts:"
cat /tmp/backend_logs.txt | tail -20

# Clean up
rm -f /tmp/backend_logs.txt

echo "✅ 500 error trigger test completed"
EOF