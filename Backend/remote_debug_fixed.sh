#!/bin/bash
# Fixed remote script to add debug endpoint

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🔧 Investigating backend structure..."

# Find the correct backend directory
if [ -d "/home/ubuntu/mydscvr-backend" ]; then
    BACKEND_ROOT="/home/ubuntu/mydscvr-backend"
    echo "✅ Found backend at: $BACKEND_ROOT"
elif [ -d "/home/ubuntu/backend" ]; then
    BACKEND_ROOT="/home/ubuntu/backend"
    echo "✅ Found backend at: $BACKEND_ROOT"
else
    echo "❌ Backend directory not found"
    ls -la /home/ubuntu/
    exit 1
fi

# Check the actual structure
echo "📁 Backend structure:"
ls -la $BACKEND_ROOT/

# Find the correct python environment
if [ -d "$BACKEND_ROOT/venv" ]; then
    VENV_PATH="$BACKEND_ROOT/venv"
elif [ -d "$BACKEND_ROOT/Backend/venv" ]; then
    VENV_PATH="$BACKEND_ROOT/Backend/venv"
else
    echo "❌ Virtual environment not found"
    exit 1
fi

echo "🐍 Using venv at: $VENV_PATH"

# Find the correct Backend code directory
if [ -f "$BACKEND_ROOT/main.py" ]; then
    CODE_DIR="$BACKEND_ROOT"
elif [ -f "$BACKEND_ROOT/Backend/main.py" ]; then
    CODE_DIR="$BACKEND_ROOT/Backend"
else
    echo "❌ main.py not found"
    find $BACKEND_ROOT -name "main.py" 2>/dev/null
    exit 1
fi

echo "📝 Using code directory: $CODE_DIR"

# Check if debug files are available
echo "🔍 Checking for debug files in code directory..."
ls -la $CODE_DIR/ | grep debug

# Try to pull latest changes first
echo "📥 Pulling latest changes..."
cd $BACKEND_ROOT
git pull origin main

# Now try to add debug endpoint if the file exists
if [ -f "$CODE_DIR/add_advice_debug_endpoint.py" ]; then
    echo "📝 Adding debug endpoint..."
    cd $CODE_DIR
    source $VENV_PATH/bin/activate
    python add_advice_debug_endpoint.py
    
    # Restart service
    echo "🔄 Restarting backend service..."
    sudo systemctl restart mydscvr-backend
    sleep 5
    
    echo "🧪 Testing debug endpoint..."
    curl -s https://mydscvr.xyz/api/advice/debug -X POST \
      -H "Content-Type: application/json" \
      -d '{"test": "debug"}' | head -c 100
else
    echo "❌ Debug script not found at $CODE_DIR/add_advice_debug_endpoint.py"
    echo "Available files:"
    ls -la $CODE_DIR/
fi

echo "✅ Debug investigation completed"
EOF