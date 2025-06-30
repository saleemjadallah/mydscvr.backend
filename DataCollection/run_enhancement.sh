#!/bin/bash

# One-time script to enhance existing events collection
# with social media, event URLs, and other advanced fields

echo "🚀 Starting existing events enhancement..."
echo "=================================="

# Change to script directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install required packages
echo "📚 Installing required packages..."
pip install -q pymongo loguru python-dotenv httpx asyncio

# Run the enhancement script with different options
echo ""
echo "Choose enhancement option:"
echo "1. Test run (enhance 10 events only)"
echo "2. Small batch (enhance 50 events)"
echo "3. Medium batch (enhance 200 events)" 
echo "4. Full enhancement (all events - may take hours)"
echo "5. Dry run (show what would be enhanced)"
echo ""

read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "🧪 Running test enhancement (10 events)..."
        python3 enhance_existing_events.py --limit 10 --batch-size 3
        ;;
    2)
        echo "📦 Running small batch enhancement (50 events)..."
        python3 enhance_existing_events.py --limit 50 --batch-size 5
        ;;
    3)
        echo "📈 Running medium batch enhancement (200 events)..."
        python3 enhance_existing_events.py --limit 200 --batch-size 5
        ;;
    4)
        echo "🔥 Running full enhancement (all events)..."
        echo "⚠️  This may take several hours. Continue? (y/N)"
        read -p "> " confirm
        if [[ $confirm == [yY] ]]; then
            python3 enhance_existing_events.py --batch-size 5
        else
            echo "❌ Enhancement cancelled"
            exit 1
        fi
        ;;
    5)
        echo "🧪 Running dry run..."
        python3 enhance_existing_events.py --dry-run --limit 10
        ;;
    *)
        echo "❌ Invalid choice. Exiting..."
        exit 1
        ;;
esac

echo ""
echo "✅ Enhancement completed!"
echo "📋 Check enhance_existing_events.log for detailed logs"