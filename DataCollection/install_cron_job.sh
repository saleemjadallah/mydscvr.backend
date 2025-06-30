#!/bin/bash

# Install cron job for Dubai Events Collection with AI Image Generation
# Run this script on the production server to set up the 1AM UTC daily job

echo "🕐 Installing DXB Events Collection Cron Job (1AM UTC Daily)"
echo "============================================================="

# Get the absolute path to the collection script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION_SCRIPT="$SCRIPT_DIR/run_collection_with_ai.sh"

echo "📂 Script directory: $SCRIPT_DIR"
echo "🔧 Collection script: $COLLECTION_SCRIPT"

# Verify the collection script exists
if [ ! -f "$COLLECTION_SCRIPT" ]; then
    echo "❌ Collection script not found: $COLLECTION_SCRIPT"
    exit 1
fi

# Make sure the script is executable
chmod +x "$COLLECTION_SCRIPT"
echo "✅ Made collection script executable"

# Create the cron job entry
CRON_ENTRY="0 1 * * * $COLLECTION_SCRIPT >> $SCRIPT_DIR/logs/cron_output.log 2>&1"

echo "📝 Cron entry to install:"
echo "   $CRON_ENTRY"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_collection_with_ai.sh"; then
    echo "⚠️ Cron job already exists. Updating..."
    # Remove existing entry and add new one
    (crontab -l 2>/dev/null | grep -v "run_collection_with_ai.sh"; echo "$CRON_ENTRY") | crontab -
else
    echo "➕ Installing new cron job..."
    # Add new entry to existing crontab
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
fi

echo "✅ Cron job installed successfully!"
echo ""
echo "📋 Current crontab:"
crontab -l
echo ""
echo "🕐 The collection will run daily at 1:00 AM UTC"
echo "📊 Pipeline includes:"
echo "   📡 Perplexity AI event discovery"
echo "   🔥 Firecrawl MCP supplemental extraction"  
echo "   💾 Event deduplication and storage"
echo "   🎨 AI image generation with DALL-E 3"
echo ""
echo "📝 Logs will be written to:"
echo "   $SCRIPT_DIR/logs/cron_execution.log"
echo "   $SCRIPT_DIR/logs/cron_output.log"
echo ""
echo "🎉 Setup complete! The automated collection with AI images is now active."