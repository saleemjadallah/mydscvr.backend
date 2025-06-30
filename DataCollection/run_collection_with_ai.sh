#!/bin/bash

# Dubai Events Collection Pipeline with AI Image Generation
# Runs daily at 1AM UTC via cron job
# Location: /home/ubuntu/DXB-events/DataCollection/run_collection_with_ai.sh

# Configuration
SCRIPT_DIR="$(dirname "$0")"
LOG_FILE="logs/cron_execution.log"
COLLECTION_SCRIPT="enhanced_collection.py"

# Ensure log directory exists
mkdir -p "$SCRIPT_DIR/logs"

# Function to log with timestamp
log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $1" | tee -a "$SCRIPT_DIR/$LOG_FILE"
}

# Change to script directory
cd "$SCRIPT_DIR" || {
    log_with_timestamp "❌ FATAL: Cannot change to script directory: $SCRIPT_DIR"
    exit 1
}

log_with_timestamp "========================================="
log_with_timestamp "🚀 STARTING DXB EVENTS COLLECTION WITH AI"
log_with_timestamp "Started at: $(date '+%Y-%m-%d %H:%M:%S UTC')"
log_with_timestamp "========================================="

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    log_with_timestamp "🔧 Activating virtual environment..."
    source venv/bin/activate
    
    if [ "$VIRTUAL_ENV" ]; then
        log_with_timestamp "✅ Virtual environment activated: $VIRTUAL_ENV"
    else
        log_with_timestamp "❌ Virtual environment activation failed"
        exit 1
    fi
else
    log_with_timestamp "❌ Virtual environment not found"
    exit 1
fi

# Check AI image generation configuration
log_with_timestamp "=== AI IMAGE GENERATION CONFIG ===" 
if [ -f "DataCollection.env" ]; then
    AI_ENABLED=$(grep "ENABLE_AI_IMAGE_GENERATION" "DataCollection.env" | cut -d'=' -f2)
    BATCH_SIZE=$(grep "AI_IMAGE_BATCH_SIZE" "DataCollection.env" | cut -d'=' -f2)
    BATCH_DELAY=$(grep "AI_IMAGE_BATCH_DELAY" "DataCollection.env" | cut -d'=' -f2)
    
    log_with_timestamp "🎨 AI Image Generation: $AI_ENABLED"
    log_with_timestamp "📦 AI Batch Size: $BATCH_SIZE"
    log_with_timestamp "⏱️ AI Batch Delay: ${BATCH_DELAY}s"
    
    if grep -q "OPENAI_API_KEY" "DataCollection.env"; then
        log_with_timestamp "🔑 OpenAI API Key: Configured"
    else
        log_with_timestamp "❌ OpenAI API Key: Missing"
    fi
fi

# Run the enhanced collection with AI image generation
log_with_timestamp "🚀 Starting enhanced collection pipeline..."
log_with_timestamp "Pipeline includes:"
log_with_timestamp "   📡 Phase 1: Perplexity AI event discovery"
log_with_timestamp "   🔥 Phase 2: Firecrawl MCP supplemental extraction"
log_with_timestamp "   💾 Phase 2.5: Event deduplication and storage"  
log_with_timestamp "   🎨 Phase 3: AI image generation with DALL-E 3"

# Execute the collection script
python "$COLLECTION_SCRIPT" 2>&1 | while IFS= read -r line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] PIPELINE: $line" | tee -a "$SCRIPT_DIR/$LOG_FILE"
done

# Capture exit code
PYTHON_EXIT_CODE=${PIPESTATUS[0]}

log_with_timestamp "=== COLLECTION COMPLETED ==="
log_with_timestamp "End time: $(date '+%Y-%m-%d %H:%M:%S UTC')"
log_with_timestamp "Exit code: $PYTHON_EXIT_CODE"

if [ $PYTHON_EXIT_CODE -eq 0 ]; then
    log_with_timestamp "✅ SUCCESS: Dubai Events collection with AI images completed successfully"
else
    log_with_timestamp "❌ FAILURE: Collection failed with exit code $PYTHON_EXIT_CODE"
fi

log_with_timestamp "========================================="
log_with_timestamp "🏁 DXB EVENTS COLLECTION COMPLETED"
log_with_timestamp "========================================="

exit $PYTHON_EXIT_CODE