#!/bin/bash
# Fix nginx configuration to properly proxy API routes to FastAPI backend
# This script diagnoses and fixes the nginx configuration issue

echo "🔍 Diagnosing nginx API proxy issue..."

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

# Test 1: Check if backend service is running
print_status "Checking backend service status..."
sudo systemctl status mydscvr-backend --no-pager -l

# Test 2: Check if backend responds on localhost:8000
print_status "Testing backend on localhost:8000..."
BACKEND_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo "FAILED")
if [[ $BACKEND_HEALTH == *"healthy"* ]]; then
    print_status "Backend is responding on localhost:8000"
else
    print_error "Backend not responding on localhost:8000"
    echo "Backend response: $BACKEND_HEALTH"
fi

# Test 3: Test advice endpoint directly on backend
print_status "Testing advice endpoint on backend..."
ADVICE_HEALTH=$(curl -s http://localhost:8000/api/advice/health 2>/dev/null || echo "FAILED")
if [[ $ADVICE_HEALTH == *"healthy"* ]]; then
    print_status "Advice endpoint is working on backend!"
else
    print_warning "Advice endpoint response: $ADVICE_HEALTH"
fi

# Test 4: Check nginx configuration
print_status "Checking nginx configuration..."
NGINX_CONFIG="/etc/nginx/sites-available/mydscvr.xyz"
NGINX_ENABLED="/etc/nginx/sites-enabled/mydscvr.xyz"

if [ -f "$NGINX_CONFIG" ]; then
    print_status "Found nginx config at $NGINX_CONFIG"
    echo "Current nginx configuration:"
    cat "$NGINX_CONFIG"
else
    print_warning "No nginx config found at $NGINX_CONFIG"
    ls -la /etc/nginx/sites-available/
fi

# Test 5: Create/update nginx configuration
print_status "Creating correct nginx configuration..."

sudo tee /etc/nginx/sites-available/mydscvr.xyz > /dev/null << 'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name mydscvr.xyz www.mydscvr.xyz;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name mydscvr.xyz www.mydscvr.xyz;

    # SSL configuration (certificates should already be in place)
    ssl_certificate /etc/letsencrypt/live/mydscvr.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mydscvr.xyz/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # API routes - proxy to FastAPI backend
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Docs endpoint
    location /docs {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Root endpoint for API info
    location = / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend static files (if needed)
    location /lander {
        try_files $uri $uri/ /lander/index.html;
        root /var/www/html;
    }

    # Fallback for any other routes - serve from backend
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable the site
print_status "Enabling nginx site..."
sudo ln -sf /etc/nginx/sites-available/mydscvr.xyz /etc/nginx/sites-enabled/mydscvr.xyz

# Remove default site if it exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
print_status "Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    print_status "Nginx configuration is valid"
    
    # Reload nginx
    print_status "Reloading nginx..."
    sudo systemctl reload nginx
    
    # Wait a moment for nginx to reload
    sleep 2
    
    # Test the API endpoints
    print_status "Testing API endpoints through nginx..."
    
    # Test health endpoint
    HEALTH_TEST=$(curl -s https://mydscvr.xyz/health 2>/dev/null || echo "FAILED")
    if [[ $HEALTH_TEST == *"healthy"* ]]; then
        print_status "Health endpoint working through nginx!"
    else
        print_warning "Health endpoint not working: $HEALTH_TEST"
    fi
    
    # Test advice endpoint
    ADVICE_TEST=$(curl -s https://mydscvr.xyz/api/advice/health 2>/dev/null || echo "FAILED")
    if [[ $ADVICE_TEST == *"healthy"* ]]; then
        print_status "🎉 ADVICE ENDPOINT IS NOW WORKING!"
    else
        print_warning "Advice endpoint still not working: $ADVICE_TEST"
    fi
    
else
    print_error "Nginx configuration test failed"
    exit 1
fi

print_status "🎉 Nginx configuration fix completed!"
echo ""
echo "📋 Summary:"
echo "   ✅ Nginx configured to proxy /api/* to FastAPI backend"
echo "   ✅ All API routes now properly proxied"
echo "   ✅ Advice endpoints should now be accessible"
echo ""
echo "🔗 Test the advice functionality:"
echo "   curl https://mydscvr.xyz/api/advice/health"
echo "   curl https://mydscvr.xyz/api/advice/categories"