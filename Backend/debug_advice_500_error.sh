#!/bin/bash
# Debug script to investigate 500 errors when creating advice

echo "🔍 Debugging advice creation 500 errors..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check backend service logs
print_status "Checking recent backend service logs..."
sudo journalctl -u mydscvr-backend --since "5 minutes ago" -n 50 --no-pager

echo ""
print_status "Checking backend log file..."
if [ -f "/home/ubuntu/mydscvr-backend/Backend/backend.log" ]; then
    tail -20 /home/ubuntu/mydscvr-backend/Backend/backend.log
else
    print_warning "Backend log file not found at expected location"
fi

echo ""
print_status "Checking if backend process is running..."
ps aux | grep uvicorn | grep -v grep

echo ""
print_status "Testing backend health on localhost..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health 2>/dev/null || echo "FAILED")
echo "Health response: $HEALTH_RESPONSE"

echo ""
print_status "Testing advice health endpoint on localhost..."
ADVICE_HEALTH=$(curl -s http://localhost:8000/api/advice/health 2>/dev/null || echo "FAILED")
echo "Advice health response: $ADVICE_HEALTH"

echo ""
print_status "Testing MongoDB connection..."
# Create a simple MongoDB test script
cat > /tmp/test_mongo.py << 'EOF'
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys

async def test_mongo():
    try:
        # Load environment variables
        import subprocess
        result = subprocess.run(['bash', '-c', 'source Backend.env && env'], 
                               capture_output=True, text=True, cwd='/home/ubuntu/mydscvr-backend/Backend')
        
        env_vars = {}
        for line in result.stdout.split('\n'):
            if '=' in line and not line.startswith('_'):
                key, value = line.split('=', 1)
                env_vars[key] = value
        
        mongodb_url = env_vars.get('MONGODB_URL', 'Not found')
        print(f"MongoDB URL configured: {mongodb_url[:20]}...")
        
        # Test connection
        client = AsyncIOMotorClient(mongodb_url)
        await client.admin.command('ping')
        print("✅ MongoDB connection successful")
        
        # Test events collection
        db = client[env_vars.get('MONGODB_DATABASE', 'DXB')]
        events_count = await db.events.count_documents({})
        print(f"✅ Events collection accessible: {events_count} events")
        
        # Test advice collection
        advice_count = await db.event_advice.count_documents({})
        print(f"✅ Advice collection accessible: {advice_count} advice entries")
        
        client.close()
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_mongo())
EOF

cd /home/ubuntu/mydscvr-backend
source venv/bin/activate
python /tmp/test_mongo.py
rm /tmp/test_mongo.py

echo ""
print_status "Testing authentication endpoints..."
AUTH_TEST=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:8000/api/auth/register" -X POST -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"testpass123","first_name":"Test"}')
echo "Auth register endpoint status: $AUTH_TEST"

echo ""
print_status "Checking FastAPI app initialization..."
cd /home/ubuntu/mydscvr-backend/Backend
python -c "
try:
    import main
    print('✅ Main module imports successfully')
    app = main.app
    print('✅ FastAPI app created successfully')
    print(f'Routes: {len(app.routes)} routes configured')
    
    # Check if advice router is included
    advice_routes = [route for route in app.routes if hasattr(route, 'path') and '/advice' in route.path]
    print(f'✅ Advice routes found: {len(advice_routes)}')
    for route in advice_routes[:5]:  # Show first 5
        print(f'  - {route.methods} {route.path}')
    
except Exception as e:
    print(f'❌ Error importing main: {e}')
    import traceback
    traceback.print_exc()
"

echo ""
print_status "Recent error logs from systemd..."
sudo journalctl -u mydscvr-backend --since "10 minutes ago" | grep -i error | tail -10

echo ""
print_status "🎯 Debug summary completed"
echo "Check the output above for:"
echo "  1. MongoDB connection issues"
echo "  2. Authentication/JWT token problems"  
echo "  3. FastAPI route configuration"
echo "  4. Recent error messages in logs"