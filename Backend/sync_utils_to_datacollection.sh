#!/bin/bash
# Sync utils from mydscvr.backend to mydscvr.datacollection
# This ensures datacollection always has the latest utils

set -e

echo "🔄 Syncing utils between backend and datacollection repos..."

# Define paths
BACKEND_PATH="/home/ubuntu/backend"
DATACOLLECTION_PATH="/home/ubuntu/mydscvr-datacollection"
TEMP_BACKEND="/tmp/mydscvr-backend-sync"

# Method 1: If both repos are on same server (current situation)
if [ -d "$BACKEND_PATH/utils" ] && [ -d "$DATACOLLECTION_PATH" ]; then
    echo "📁 Syncing from local backend repo..."
    
    # Backup existing utils in datacollection
    if [ -d "$DATACOLLECTION_PATH/utils" ]; then
        echo "💾 Backing up existing utils..."
        cp -r "$DATACOLLECTION_PATH/utils" "$DATACOLLECTION_PATH/utils.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Copy utils from backend to datacollection
    echo "📋 Copying utils from backend..."
    cp -r "$BACKEND_PATH/utils" "$DATACOLLECTION_PATH/"
    
    echo "✅ Local sync completed"

# Method 2: If backend repo not available locally, clone from GitHub
else
    echo "🌐 Cloning backend repo for utils sync..."
    
    # Clean up any existing temp directory
    rm -rf "$TEMP_BACKEND"
    
    # Clone backend repo to temp location
    git clone https://github.com/saleemjadallah/mydscvr.backend.git "$TEMP_BACKEND"
    
    # Navigate to datacollection directory
    cd "$DATACOLLECTION_PATH"
    
    # Backup existing utils
    if [ -d "utils" ]; then
        echo "💾 Backing up existing utils..."
        cp -r utils "utils.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Copy utils from cloned backend
    echo "📋 Copying utils from backend repo..."
    cp -r "$TEMP_BACKEND/utils" ./
    
    # Clean up temp directory
    rm -rf "$TEMP_BACKEND"
    
    echo "✅ Remote sync completed"
fi

# Verify utils were copied correctly
if [ -d "$DATACOLLECTION_PATH/utils" ]; then
    echo "🧪 Verifying utils sync..."
    cd "$DATACOLLECTION_PATH"
    
    # List key utils files
    echo "📄 Key utils files found:"
    find utils/ -name "*.py" | head -10
    
    # Test import if virtual environment exists
    if [ -d "venv" ]; then
        source venv/bin/activate
        python -c "
try:
    from utils.mongodb_singleton import MongoDBSingleton
    print('✅ Utils import test successful')
except Exception as e:
    print(f'⚠️ Utils import test failed: {e}')
" 2>/dev/null || echo "⚠️ Could not test utils import"
    fi
    
    echo "✅ Utils sync verification completed"
else
    echo "❌ Utils sync failed - directory not found"
    exit 1
fi

echo "🎉 Utils sync completed successfully!" 