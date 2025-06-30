#!/bin/bash

# Enhanced Cron Logging Script for DXB Events Collection
# Provides detailed logging to debug 1AM UTC cron job failures
# Location: /home/ubuntu/DXB-events/DataCollection/test_cron_logging.sh

# Configuration
LOG_FILE="logs/cron_execution.log"
MAIN_LOG="logs/collection.log"
ERROR_LOG="logs/cron_errors.log"
SCRIPT_DIR="$(dirname "$0")"
PYTHON_SCRIPT="enhanced_collection.py"

# Ensure log directory exists
mkdir -p "$SCRIPT_DIR/logs"

# Function to log with timestamp
log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] $1" | tee -a "$SCRIPT_DIR/$LOG_FILE"
}

# Function to log system resources
log_system_resources() {
    log_with_timestamp "=== SYSTEM RESOURCES ==="
    log_with_timestamp "Memory Usage: $(free -h | grep '^Mem:' | awk '{print $3"/"$2}')"
    log_with_timestamp "Disk Usage: $(df -h / | tail -1 | awk '{print $5}')"
    log_with_timestamp "Load Average: $(uptime | awk -F'load average:' '{print $2}')"
    log_with_timestamp "Active Processes: $(ps aux | wc -l)"
}

# Function to log environment info
log_environment_info() {
    log_with_timestamp "=== ENVIRONMENT INFO ==="
    log_with_timestamp "Current User: $(whoami)"
    log_with_timestamp "Current Directory: $(pwd)"
    log_with_timestamp "Python Path: $(which python)"
    log_with_timestamp "Python Version: $(python --version 2>&1)"
    log_with_timestamp "Virtual Env: ${VIRTUAL_ENV:-'Not activated'}"
    log_with_timestamp "PATH: $PATH"
}

# Function to check dependencies
check_dependencies() {
    log_with_timestamp "=== DEPENDENCY CHECK ==="
    
    # Check if Python script exists
    if [ -f "$SCRIPT_DIR/$PYTHON_SCRIPT" ]; then
        log_with_timestamp "✅ Python script exists: $PYTHON_SCRIPT"
        log_with_timestamp "Script permissions: $(ls -la "$SCRIPT_DIR/$PYTHON_SCRIPT" | awk '{print $1}')"
        log_with_timestamp "Script size: $(ls -lh "$SCRIPT_DIR/$PYTHON_SCRIPT" | awk '{print $5}')"
        log_with_timestamp "Last modified: $(ls -l "$SCRIPT_DIR/$PYTHON_SCRIPT" | awk '{print $6, $7, $8}')"
    else
        log_with_timestamp "❌ Python script missing: $PYTHON_SCRIPT"
        exit 1
    fi
    
    # Check virtual environment
    if [ -d "$SCRIPT_DIR/venv" ]; then
        log_with_timestamp "✅ Virtual environment exists"
        log_with_timestamp "Venv size: $(du -sh "$SCRIPT_DIR/venv" | awk '{print $1}')"
    else
        log_with_timestamp "❌ Virtual environment missing"
        exit 1
    fi
    
    # Check environment files
    for env_file in "DataCollection.env" ".env" "AI_API.env" "Mongo.env"; do
        if [ -f "$SCRIPT_DIR/$env_file" ]; then
            log_with_timestamp "✅ Environment file exists: $env_file"
        else
            log_with_timestamp "⚠️ Environment file missing: $env_file"
        fi
    done
    
    # Check AI image generation configuration
    log_with_timestamp "=== AI IMAGE GENERATION CONFIG ==="
    if [ -f "$SCRIPT_DIR/DataCollection.env" ]; then
        if grep -q "ENABLE_AI_IMAGE_GENERATION" "$SCRIPT_DIR/DataCollection.env"; then
            AI_ENABLED=$(grep "ENABLE_AI_IMAGE_GENERATION" "$SCRIPT_DIR/DataCollection.env" | cut -d'=' -f2)
            log_with_timestamp "🎨 AI Image Generation: $AI_ENABLED"
        fi
        if grep -q "OPENAI_API_KEY" "$SCRIPT_DIR/DataCollection.env"; then
            log_with_timestamp "🔑 OpenAI API Key: Configured"
        else
            log_with_timestamp "❌ OpenAI API Key: Missing"
        fi
        if grep -q "AI_IMAGE_BATCH_SIZE" "$SCRIPT_DIR/DataCollection.env"; then
            BATCH_SIZE=$(grep "AI_IMAGE_BATCH_SIZE" "$SCRIPT_DIR/DataCollection.env" | cut -d'=' -f2)
            log_with_timestamp "📦 AI Batch Size: $BATCH_SIZE"
        fi
    fi
}

# Function to test network connectivity
test_connectivity() {
    log_with_timestamp "=== CONNECTIVITY TEST ==="
    
    # Test MongoDB connection
    if ping -c 1 dxb.tq60png.mongodb.net >/dev/null 2>&1; then
        log_with_timestamp "✅ MongoDB host reachable"
    else
        log_with_timestamp "❌ MongoDB host unreachable"
    fi
    
    # Test Perplexity API
    if ping -c 1 api.perplexity.ai >/dev/null 2>&1; then
        log_with_timestamp "✅ Perplexity API host reachable"
    else
        log_with_timestamp "❌ Perplexity API host unreachable"
    fi
    
    # Test general internet
    if ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        log_with_timestamp "✅ Internet connectivity OK"
    else
        log_with_timestamp "❌ No internet connectivity"
    fi
}

# Main execution
main() {
    log_with_timestamp "========================================="
    log_with_timestamp "🚀 STARTING CRON JOB EXECUTION"
    log_with_timestamp "Triggered at: $(date '+%Y-%m-%d %H:%M:%S UTC')"
    log_with_timestamp "========================================="
    
    # Change to script directory
    cd "$SCRIPT_DIR" || {
        log_with_timestamp "❌ FATAL: Cannot change to script directory: $SCRIPT_DIR"
        exit 1
    }
    
    # Log system info
    log_system_resources
    log_environment_info
    check_dependencies
    test_connectivity
    
    log_with_timestamp "=== VIRTUAL ENVIRONMENT ACTIVATION ==="
    
    # Activate virtual environment with detailed logging
    if [ -f "venv/bin/activate" ]; then
        log_with_timestamp "🔧 Activating virtual environment..."
        source venv/bin/activate
        
        if [ "$VIRTUAL_ENV" ]; then
            log_with_timestamp "✅ Virtual environment activated: $VIRTUAL_ENV"
            log_with_timestamp "Python path after activation: $(which python)"
            log_with_timestamp "Pip path after activation: $(which pip)"
        else
            log_with_timestamp "❌ Virtual environment activation failed"
            exit 1
        fi
    else
        log_with_timestamp "❌ Virtual environment activation script not found"
        exit 1
    fi
    
    log_with_timestamp "=== PYTHON DEPENDENCIES CHECK ==="
    
    # Check Python packages
    log_with_timestamp "Checking required packages..."
    python -c "
import sys
packages = ['pymongo', 'loguru', 'python-dotenv', 'httpx', 'asyncio', 'pydantic', 'pydantic_settings']
for pkg in packages:
    try:
        __import__(pkg)
        print(f'✅ {pkg}: Available')
    except ImportError as e:
        print(f'❌ {pkg}: Missing - {e}')
        sys.exit(1)
" 2>&1 | while read line; do
        log_with_timestamp "$line"
    done
    
    # Check if the dependency check failed
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_with_timestamp "❌ FATAL: Python dependencies check failed"
        exit 1
    fi
    
    log_with_timestamp "=== STARTING PYTHON SCRIPT ==="
    log_with_timestamp "Executing: python $PYTHON_SCRIPT"
    log_with_timestamp "Start time: $(date '+%Y-%m-%d %H:%M:%S UTC')"
    
    # Execute the Python script with detailed logging
    python "$PYTHON_SCRIPT" 2>&1 | while IFS= read -r line; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S UTC')] PYTHON: $line" | tee -a "$SCRIPT_DIR/$LOG_FILE" "$SCRIPT_DIR/$MAIN_LOG"
    done
    
    # Capture exit code
    PYTHON_EXIT_CODE=${PIPESTATUS[0]}
    
    log_with_timestamp "=== EXECUTION COMPLETED ==="
    log_with_timestamp "End time: $(date '+%Y-%m-%d %H:%M:%S UTC')"
    log_with_timestamp "Python script exit code: $PYTHON_EXIT_CODE"
    
    if [ $PYTHON_EXIT_CODE -eq 0 ]; then
        log_with_timestamp "✅ SUCCESS: Python script completed successfully"
    else
        log_with_timestamp "❌ FAILURE: Python script failed with exit code $PYTHON_EXIT_CODE"
        
        # Log recent error lines if they exist
        if [ -f "$SCRIPT_DIR/$ERROR_LOG" ]; then
            log_with_timestamp "Recent errors from error log:"
            tail -20 "$SCRIPT_DIR/$ERROR_LOG" | while read line; do
                log_with_timestamp "ERROR: $line"
            done
        fi
    fi
    
    # Final system resources
    log_with_timestamp "=== FINAL SYSTEM STATE ==="
    log_system_resources
    
    log_with_timestamp "========================================="
    log_with_timestamp "🏁 CRON JOB EXECUTION COMPLETED"
    log_with_timestamp "Total execution time: $(($(date +%s) - $(date -d "$(head -1 "$SCRIPT_DIR/$LOG_FILE" | cut -d']' -f1 | tr -d '[')" +%s))) seconds"
    log_with_timestamp "========================================="
    
    exit $PYTHON_EXIT_CODE
}

# Execute main function
main "$@"