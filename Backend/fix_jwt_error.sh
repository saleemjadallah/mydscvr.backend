#!/bin/bash
# Fix JWT error causing 500 internal server error

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🔧 Fixing JWT error causing 500 internal server error..."

cd /home/ubuntu/backend

# Check current JWT library version
echo "📋 Current JWT library version:"
source venv/bin/activate
pip show PyJWT || pip show jwt

# Check the auth dependencies file
echo "📋 Checking auth dependencies file:"
if [ -f "utils/auth_dependencies.py" ]; then
    grep -n "JWTError" utils/auth_dependencies.py
else
    find . -name "*.py" -exec grep -l "JWTError" {} \;
fi

# The fix: PyJWT v2+ uses jwt.exceptions.JWTError instead of jwt.JWTError
echo "🔧 Creating fix for JWT error..."

# Find the file with JWTError usage
AUTH_FILE=$(find . -name "*.py" -exec grep -l "jwt.JWTError" {} \; | head -1)
if [ -n "$AUTH_FILE" ]; then
    echo "📝 Found JWT error in: $AUTH_FILE"
    
    # Backup the file
    cp "$AUTH_FILE" "${AUTH_FILE}.backup"
    
    # Fix the import and usage
    sed -i 's/import jwt$/import jwt\nfrom jwt.exceptions import InvalidTokenError/' "$AUTH_FILE"
    sed -i 's/jwt\.JWTError/InvalidTokenError/g' "$AUTH_FILE"
    
    echo "✅ Fixed JWT error in $AUTH_FILE"
    
    # Show the changes
    echo "📋 Changes made:"
    grep -A 2 -B 2 "InvalidTokenError\|import jwt" "$AUTH_FILE"
else
    echo "❌ Could not find file with jwt.JWTError"
    # Alternative approach - search more broadly
    echo "🔍 Searching for JWT usage..."
    grep -r "JWTError" . --include="*.py" | head -5
fi

# Restart the service
echo "🔄 Restarting backend service..."
sudo systemctl restart mydscvr-backend

# Wait for restart
sleep 5

# Check service status
echo "📊 Service status:"
sudo systemctl status mydscvr-backend --no-pager -l | tail -5

echo "✅ JWT fix completed"
EOF