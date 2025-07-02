#!/bin/bash
# Portable Cron Health Monitor for DXB Events Collection
# This script detects its environment and ensures everything is ready
# Usage: ./cron_health_monitor.sh [work_directory]

set -e

# Get current directory or use provided argument
CURRENT_DIR=$(pwd)
WORK_DIR="${1:-$CURRENT_DIR}"

# Auto-detect environment based on current location
if [[ "$WORK_DIR" == *"mydscvr-datacollection"* ]]; then
    BACKUP_DIR="/home/ubuntu/DXB-events/DataCollection"
    ENVIRONMENT="mydscvr-datacollection"
elif [[ "$WORK_DIR" == *"DataCollection"* ]]; then
    BACKUP_DIR="/home/ubuntu/mydscvr-datacollection"
    ENVIRONMENT="DXB-events/DataCollection"
else
    # Default to mydscvr-datacollection if run from elsewhere
    WORK_DIR="/home/ubuntu/mydscvr-datacollection"
    BACKUP_DIR="/home/ubuntu/DXB-events/DataCollection"
    ENVIRONMENT="mydscvr-datacollection (default)"
fi

LOG_FILE="$WORK_DIR/logs/health_monitor.log"

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S UTC'): $1" | tee -a "$LOG_FILE"
}

log "🔍 Starting health check for environment: $ENVIRONMENT"
log "📁 Working directory: $WORK_DIR"
log "📁 Backup directory: $BACKUP_DIR"

# Check if primary directory exists
if [ ! -d "$WORK_DIR" ]; then
    log "❌ ERROR: Working directory $WORK_DIR not found!"
    exit 1
fi

cd "$WORK_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    log "❌ ERROR: Virtual environment not found. Creating new one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install httpx loguru pymongo motor python-dotenv aiohttp tenacity asyncio-throttle
    log "✅ Virtual environment created and dependencies installed"
else
    source venv/bin/activate
fi

# Test critical imports
log "🧪 Testing critical dependencies..."
python -c "
try:
    import httpx, loguru, pymongo, motor, aiohttp, tenacity, asyncio_throttle
    print('✅ All critical imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
" 2>&1 | tee -a "$LOG_FILE"

IMPORT_TEST=$?
if [ $IMPORT_TEST -ne 0 ]; then
    log "❌ Import test failed. Installing missing dependencies..."
    pip install httpx loguru pymongo motor python-dotenv aiohttp tenacity asyncio-throttle
    pip install pydantic requests jsonschema python-dateutil
    log "✅ Dependencies reinstalled"
fi

# Check essential files
log "📂 Checking essential files..."

if [ ! -f "DataCollection.env" ]; then
    log "⚠️ DataCollection.env missing. Copying from backup..."
    if [ -f "$BACKUP_DIR/DataCollection.env" ]; then
        cp "$BACKUP_DIR/DataCollection.env" ./
        log "✅ DataCollection.env copied"
    else
        log "❌ ERROR: DataCollection.env not found in backup location"
    fi
fi

if [ ! -f "Mongo.env" ]; then
    log "⚠️ Mongo.env missing. Copying from backup..."
    if [ -f "$BACKUP_DIR/Mongo.env" ]; then
        cp "$BACKUP_DIR/Mongo.env" ./
        log "✅ Mongo.env copied"
    else
        log "❌ ERROR: Mongo.env not found in backup location"
    fi
fi

if [ ! -d "utils" ]; then
    log "⚠️ utils directory missing. Copying from backup..."
    if [ -d "$BACKUP_DIR/utils" ]; then
        cp -r "$BACKUP_DIR/utils" ./
        log "✅ utils directory copied"
    else
        log "❌ ERROR: utils directory not found in backup location"
    fi
fi

# Check MongoDB connectivity
log "🔌 Testing MongoDB connection..."
python -c "
import asyncio
import os
from dotenv import load_dotenv

load_dotenv('Mongo.env')
load_dotenv('DataCollection.env')

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    
    async def test_mongo():
        client = AsyncIOMotorClient(os.getenv('MONGODB_URI'))
        await client.admin.command('ping')
        await client.close()
        print('✅ MongoDB connection successful')
    
    asyncio.run(test_mongo())
except Exception as e:
    print(f'❌ MongoDB connection failed: {e}')
    exit(1)
" 2>&1 | tee -a "$LOG_FILE"

MONGO_TEST=$?
if [ $MONGO_TEST -ne 0 ]; then
    log "❌ MongoDB connection test failed"
    exit 1
fi

# Check API keys
log "🔑 Checking API configuration..."
if [ -f "DataCollection.env" ]; then
    source DataCollection.env 2>/dev/null || log "⚠️ Could not source DataCollection.env"
    
    if [ -z "$PERPLEXITY_API_KEY" ]; then
        log "❌ ERROR: PERPLEXITY_API_KEY not set"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ]; then
        log "❌ ERROR: OPENAI_API_KEY not set"
        exit 1
    fi
    
    log "✅ API keys are configured"
else
    log "⚠️ DataCollection.env not found, skipping API key check"
fi

# Check disk space
DISK_USAGE=$(df /home/ubuntu | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    log "⚠️ WARNING: Disk usage is ${DISK_USAGE}% - consider cleanup"
fi

# Final test - try to import the main collection module
log "🧪 Testing main collection module..."
if [ -f "enhanced_collection.py" ]; then
    python -c "
try:
    import enhanced_collection
    print('✅ Main collection module import successful')
except Exception as e:
    print(f'❌ Main collection module import failed: {e}')
    exit(1)
" 2>&1 | tee -a "$LOG_FILE"

    MAIN_TEST=$?
    if [ $MAIN_TEST -ne 0 ]; then
        log "❌ Main collection module test failed"
        exit 1
    fi
else
    log "⚠️ enhanced_collection.py not found in current directory"
fi

log "🎉 All health checks passed! System ready for collection job."

# Clean up old log files (keep last 7 days)
find "$(dirname "$LOG_FILE")" -name "health_monitor.log.*" -mtime +7 -delete 2>/dev/null || true

exit 0 