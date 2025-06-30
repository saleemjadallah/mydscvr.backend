# DXB Events Collection - Cron Job Setup

## Overview
This document explains how to set up the automated daily collection of Dubai events with AI image generation.

## Files Created

### 1. `run_collection_with_ai.sh`
- **Purpose**: Main script that runs the complete collection pipeline
- **Schedule**: Designed to run daily at 1AM UTC
- **Features**:
  - Activates virtual environment
  - Validates AI image generation configuration
  - Runs enhanced_collection.py with full pipeline
  - Comprehensive logging with timestamps
  - Proper error handling and exit codes

### 2. `install_cron_job.sh`
- **Purpose**: One-time setup script to install the cron job
- **Usage**: Run once on production server to set up automation
- **Features**:
  - Installs cron job for 1AM UTC daily execution
  - Handles existing cron job updates
  - Validates script paths and permissions

### 3. `test_cron_logging.sh` (Updated)
- **Purpose**: Enhanced logging and validation for debugging
- **Features**:
  - Added AI image generation configuration checks
  - OpenAI API key validation
  - Batch processing settings verification

## Production Pipeline Phases

The automated collection runs these phases:

1. **Phase 1: Perplexity AI Discovery**
   - Discovers events using sophisticated AI prompts
   - Covers multiple event categories
   - High-quality event extraction

2. **Phase 2: Firecrawl MCP Supplemental**
   - Extracts from PlatinumList, TimeOut, WhatsOn
   - Configurable daily limits
   - Complementary event sources

3. **Phase 2.5: Deduplication & Storage**
   - Advanced deduplication algorithms
   - Quality scoring and filtering
   - MongoDB storage with session tracking

4. **Phase 3: AI Image Generation**
   - Hybrid prompt generation using event descriptions
   - DALL-E 3 integration with Dubai-specific enhancements
   - Batch processing with rate limiting
   - Quality analysis and fallback strategies

## Installation on Production Server

```bash
# 1. Navigate to the DataCollection directory
cd /home/ubuntu/DXB-events/DataCollection

# 2. Run the installation script
./install_cron_job.sh

# 3. Verify installation
crontab -l
```

## Configuration

### Environment Variables (DataCollection.env)
```bash
# AI Image Generation
ENABLE_AI_IMAGE_GENERATION=true
AI_IMAGE_BATCH_SIZE=5
AI_IMAGE_BATCH_DELAY=10
OPENAI_API_KEY=sk-proj-...

# Firecrawl MCP
ENABLE_FIRECRAWL_SUPPLEMENT=true
FIRECRAWL_PLATINUMLIST_LIMIT=50
FIRECRAWL_TIMEOUT_LIMIT=30
FIRECRAWL_WHATSON_LIMIT=20
```

### Daily Limits
- **Perplexity**: ~50-100 events per day
- **Firecrawl**: ~100 events per day (configurable)
- **AI Images**: All stored events get unique AI-generated images

## Monitoring

### Log Files
- `logs/cron_execution.log` - Detailed execution logs
- `logs/cron_output.log` - Cron job output
- `logs/collection.log` - Collection pipeline logs

### Manual Testing
```bash
# Test the collection pipeline
python enhanced_collection.py

# Test AI image generation only
python test_ai_generation_only.py

# Test integrated pipeline
python test_integrated_collection.py
```

## Schedule
- **Execution Time**: 12:00 AM UTC daily (4:00 AM Dubai time)
- **Expected Duration**: 15-30 minutes depending on event volume
- **Retry Logic**: Built-in retry for failed operations
- **Rate Limiting**: Respects API limits for all services

### Updated Daily Schedule (Dubai Time):
- **3:00 AM**: Pre-collection health check
- **4:00 AM**: Main collection with AI image generation
- **4:15 AM**: Hidden gems generation
- **4:30 AM**: Health monitoring  
- **6:00 AM**: Auto-deduplication
- **6:00 PM**: Evening updates collection

## Success Metrics
- Events collected and deduplicated
- AI images generated successfully
- Storage completion rate
- API usage within limits
- Log file health checks

## Troubleshooting

### Common Issues
1. **Virtual Environment**: Ensure venv is properly activated
2. **API Keys**: Verify all API keys are configured
3. **Network**: Check connectivity to MongoDB, Perplexity, OpenAI
4. **Permissions**: Ensure scripts are executable
5. **Rate Limits**: Monitor API usage and adjust batch sizes

### Debug Commands
```bash
# Check cron job status
crontab -l

# Test collection manually
./run_collection_with_ai.sh

# Check recent logs
tail -f logs/cron_execution.log
```

## Next Steps

1. **Deploy to Production**: Run `install_cron_job.sh` on production server
2. **Monitor First Run**: Check logs after first automated execution
3. **Adjust Settings**: Fine-tune batch sizes and limits based on performance
4. **Set Up Alerts**: Configure monitoring for failed executions
5. **Regular Maintenance**: Monitor log files and database growth

The automated collection system is now ready to provide daily Dubai events with AI-generated images!