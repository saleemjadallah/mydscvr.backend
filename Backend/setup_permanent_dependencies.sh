#!/bin/bash
# Portable Dependency Setup for DXB Events Data Collection
# Run this script from the server where the collection needs to be set up
# Usage: ./setup_permanent_dependencies.sh [target_directory]

set -e

echo "🔧 Setting up portable dependencies for DXB Events Collection..."

# Get current directory and target directory
CURRENT_DIR=$(pwd)
TARGET_DIR="${1:-$CURRENT_DIR}"

# Detect if we're in a known collection directory
if [[ "$CURRENT_DIR" == *"mydscvr-datacollection"* ]]; then
    WORK_DIR="$CURRENT_DIR"
    BACKUP_DIR="/home/ubuntu/DXB-events/DataCollection"
elif [[ "$CURRENT_DIR" == *"DataCollection"* ]]; then
    WORK_DIR="$CURRENT_DIR"
    BACKUP_DIR="/home/ubuntu/mydscvr-datacollection"
else
    # Default server paths
    WORK_DIR="/home/ubuntu/mydscvr-datacollection"
    BACKUP_DIR="/home/ubuntu/DXB-events/DataCollection"
fi

echo "📁 Working directory: $WORK_DIR"
echo "📁 Backup directory: $BACKUP_DIR"

# Function to setup environment
setup_environment() {
    local SETUP_DIR=$1
    echo "🔧 Setting up environment in: $SETUP_DIR"
    
    if [ ! -d "$SETUP_DIR" ]; then
        echo "❌ ERROR: Directory $SETUP_DIR not found!"
        return 1
    fi
    
    cd "$SETUP_DIR"
    
    # Create/activate virtual environment
    if [ ! -d "venv" ]; then
        echo "🆕 Creating new virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # Upgrade pip
    echo "📦 Upgrading pip..."
    pip install --upgrade pip
    
    # Install core dependencies
    echo "🔨 Installing core dependencies..."
    pip install httpx loguru pymongo motor python-dotenv aiohttp tenacity asyncio-throttle
    pip install pydantic requests jsonschema python-dateutil
    
    # Install from requirements if exists
    if [ -f "requirements.txt" ]; then
        echo "📋 Installing from requirements.txt..."
        pip install -r requirements.txt || echo "⚠️ Some requirements failed, continuing..."
    fi
    
    # Create working requirements snapshot
    echo "📸 Creating dependency snapshot..."
    pip freeze > "working_requirements_$(date +%Y%m%d).txt"
    
    # Copy essential files if missing and backup exists
    echo "📂 Ensuring essential files exist..."
    
    if [ ! -d "utils" ] && [ -d "$BACKUP_DIR/utils" ]; then
        echo "📋 Copying utils directory from $BACKUP_DIR..."
        cp -r "$BACKUP_DIR/utils" ./
    fi
    
    if [ ! -f "Mongo.env" ] && [ -f "$BACKUP_DIR/Mongo.env" ]; then
        echo "🔐 Copying Mongo.env from $BACKUP_DIR..."
        cp "$BACKUP_DIR/Mongo.env" ./
    fi
    
    if [ ! -f "DataCollection.env" ] && [ -f "$BACKUP_DIR/DataCollection.env" ]; then
        echo "🔑 Copying DataCollection.env from $BACKUP_DIR..."
        cp "$BACKUP_DIR/DataCollection.env" ./
    fi
    
    # Test imports
    echo "🧪 Testing critical imports..."
    python -c "
try:
    import httpx, loguru, pymongo, motor, aiohttp, tenacity, asyncio_throttle
    print('✅ All critical imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
" || echo "❌ Import test failed"
    
    # Test MongoDB connection if possible
    if [ -f "Mongo.env" ] && [ -f "utils/mongodb_singleton.py" ]; then
        echo "🔌 Testing MongoDB connection..."
        python -c "
try:
    from utils.mongodb_singleton import MongoDBSingleton
    print('✅ MongoDB utils import successful')
except Exception as e:
    print(f'⚠️ MongoDB test failed: {e}')
" || echo "⚠️ MongoDB test skipped"
    fi
    
    echo "✅ Environment setup completed for $SETUP_DIR"
}

# Setup primary environment
setup_environment "$WORK_DIR"

# If backup directory exists and is different, set it up too
if [ -d "$BACKUP_DIR" ] && [ "$BACKUP_DIR" != "$WORK_DIR" ]; then
    echo "🔄 Also setting up backup environment..."
    setup_environment "$BACKUP_DIR"
fi

echo "🎉 Dependency setup completed!"
echo "📝 Test with: cd $WORK_DIR && ./run_collection_with_ai.sh" 