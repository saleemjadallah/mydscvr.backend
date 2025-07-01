#!/bin/bash
# Remote nginx fix - single command to run from local machine

ssh -i /Users/saleemjadallah/Desktop/DXB-events/mydscvrkey.pem ubuntu@3.29.102.4 << 'EOF'
echo "🔧 Starting remote nginx fix..."
cd /home/ubuntu/mydscvr-backend/Backend
chmod +x fix_nginx_api_proxy.sh
sudo ./fix_nginx_api_proxy.sh
echo "✅ Remote nginx fix completed"
EOF