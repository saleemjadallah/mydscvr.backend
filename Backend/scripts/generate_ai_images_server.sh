#!/bin/bash
# Script to generate AI images on the production server
# This script assumes environment variables are properly set from GitHub secrets

echo "🚀 AI Image Generation Script for Production Server"
echo "================================================="

# Check if virtual environment exists
if [ -d "/home/ubuntu/mydscvr-backend/venv" ]; then
    echo "✅ Activating virtual environment..."
    source /home/ubuntu/mydscvr-backend/venv/bin/activate
else
    echo "❌ Virtual environment not found at /home/ubuntu/mydscvr-backend/venv"
    exit 1
fi

# Navigate to backend directory
cd /home/ubuntu/mydscvr-backend || exit 1

# Check if the production script exists
if [ ! -f "generate_images_production.py" ]; then
    echo "❌ generate_images_production.py not found"
    echo "Please ensure the script is deployed to the server"
    exit 1
fi

# Default batch size
BATCH_SIZE=${1:-50}

echo "📋 Generating AI images for $BATCH_SIZE events..."
echo "Press Ctrl+C to stop gracefully"
echo ""

# Export environment variables from Backend.env if it exists
if [ -f "Backend.env" ]; then
    echo "✅ Loading environment variables from Backend.env..."
    export $(grep -v '^#' Backend.env | xargs)
fi

# Run the Python script
python generate_images_production.py $BATCH_SIZE

echo ""
echo "✅ Image generation completed"