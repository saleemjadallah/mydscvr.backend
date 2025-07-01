#!/bin/bash
# Hotfix to add logging to advice endpoint for debugging 500 errors

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🔧 Adding logging to advice endpoint..."

cd /home/ubuntu/backend

# Backup the original file
cp routers/event_advice.py routers/event_advice.py.backup

# Add detailed logging to the create_advice_direct function
python3 << 'PYTHON_EOF'
# Read the file
with open('routers/event_advice.py', 'r') as f:
    content = f.read()

# Find the start of create_advice_direct function
start_marker = 'async def create_advice_direct('
start_pos = content.find(start_marker)

if start_pos == -1:
    print("❌ Function not found")
    exit(1)

# Find the try block
try_pos = content.find('try:', start_pos)
if try_pos == -1:
    print("❌ Try block not found")
    exit(1)

# Add logging right after the try:
insert_pos = content.find('\n', try_pos) + 1

# Logging code to insert
logging_code = '''        logger.info(f"📝 [ADVICE DEBUG] Starting advice creation")
        logger.info(f"📝 [ADVICE DEBUG] User ID: {getattr(current_user, 'id', 'NO_ID')}")
        logger.info(f"📝 [ADVICE DEBUG] User email: {getattr(current_user, 'email', 'NO_EMAIL')}")
        logger.info(f"📝 [ADVICE DEBUG] User verified: {getattr(current_user, 'is_email_verified', 'NO_VERIFIED_FIELD')}")
        logger.info(f"📝 [ADVICE DEBUG] Event ID: {advice_data.event_id}")
        logger.info(f"📝 [ADVICE DEBUG] Advice title: {advice_data.title}")
        
'''

# Insert the logging code
new_content = content[:insert_pos] + logging_code + content[insert_pos:]

# Write the modified file
with open('routers/event_advice.py', 'w') as f:
    f.write(new_content)

print("✅ Logging added to advice endpoint")
PYTHON_EOF

# Restart the service
echo "🔄 Restarting backend service..."
sudo systemctl restart mydscvr-backend

# Wait for restart
sleep 5

echo "📊 Service status:"
sudo systemctl status mydscvr-backend --no-pager -l | tail -10

echo "✅ Hotfix applied. Now test the advice creation and check logs with:"
echo "sudo journalctl -u mydscvr-backend --since '1 minute ago' -f"
EOF