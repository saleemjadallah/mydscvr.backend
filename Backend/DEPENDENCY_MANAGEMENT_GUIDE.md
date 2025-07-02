# Dependency Management Guide for DXB Events Collection

## 🚨 Critical Issue Analysis: July 2nd Failure

### What Happened?
On July 2nd, 2025, the 1AM UTC cron job **executed but failed** due to missing Python dependencies. Here's the exact timeline:

1. **June 28**: New `mydscvr-datacollection` repository was cloned
2. **June 30**: Fresh virtual environment created but dependencies never installed
3. **July 2, 00:00:01 UTC**: Cron job executed but crashed with `ModuleNotFoundError: No module named 'httpx'`

### Root Cause
- **Two separate environments**: Original working environment vs new repository environment
- **Incomplete setup**: New repository was cloned but dependencies were never installed
- **Cron job pointed to wrong environment**: Using new repository without proper setup

## 🔧 Portable Solutions Implemented

### 1. Portable Dependency Setup Script
**File**: `setup_permanent_dependencies.sh`
- **Auto-detects environment**: Works from any collection directory
- **Automatically installs all required dependencies**
- **Copies essential configuration files** from backup locations
- **Creates dependency snapshots** with timestamps
- **Tests all critical imports** to verify functionality

**Usage (on server)**:
```bash
# Option 1: Run from mydscvr-datacollection directory
cd /home/ubuntu/mydscvr-datacollection
./setup_permanent_dependencies.sh

# Option 2: Run from DXB-events/DataCollection directory  
cd /home/ubuntu/DXB-events/DataCollection
./setup_permanent_dependencies.sh

# Option 3: Run from anywhere with target directory
./setup_permanent_dependencies.sh /home/ubuntu/mydscvr-datacollection
```

### 2. Portable Health Monitoring Script
**File**: `cron_health_monitor.sh`
- **Auto-detects current environment** and backup locations
- **Runs BEFORE each collection job** to verify readiness
- **Auto-repairs common issues** without human intervention
- **Logs everything** with timestamps for troubleshooting

**Usage (on server)**:
```bash
# Run health check in current directory
cd /home/ubuntu/mydscvr-datacollection
./cron_health_monitor.sh

# Or specify target directory
./cron_health_monitor.sh /home/ubuntu/mydscvr-datacollection
```

**Recommended Crontab Setup**:
```bash
# Copy scripts to server first
59 23 * * * cd /home/ubuntu/mydscvr-datacollection && ./cron_health_monitor.sh
0 0 * * * cd /home/ubuntu/mydscvr-datacollection && ./run_collection_with_ai.sh
```

## 📋 Essential Dependencies List

### Core Python Packages
```txt
httpx>=0.28.1           # HTTP client for API calls
loguru>=0.7.3           # Logging
pymongo>=4.0.0          # MongoDB driver
motor>=3.7.1            # Async MongoDB driver
python-dotenv>=1.0.0    # Environment variable loading
aiohttp>=3.12.0         # Async HTTP client
tenacity>=8.0.0         # Retry logic
asyncio-throttle>=1.0.2 # Rate limiting
pydantic>=2.0.0         # Data validation
requests>=2.31.0        # HTTP client
jsonschema>=4.24.0      # JSON validation
python-dateutil>=2.8.0  # Date parsing
```

### Essential Files (Auto-detected)
```
📁 mydscvr-datacollection/ (Primary Environment)
├── 📄 DataCollection.env    # API keys and configuration
├── 📄 Mongo.env             # MongoDB connection string
├── 📁 utils/                # Utility modules
├── 📁 venv/                 # Virtual environment
└── 📄 enhanced_collection.py # Main collection script

📁 DXB-events/DataCollection/ (Backup Environment)
├── 📄 DataCollection.env    # Backup configuration
├── 📄 Mongo.env             # Backup MongoDB config
├── 📁 utils/                # Backup utility modules
└── 📁 venv/                 # Backup virtual environment
```

## 🛡️ How Scripts Work (Portable Design)

### Auto-Detection Logic
The scripts automatically detect which environment they're running in:

1. **If current directory contains "mydscvr-datacollection"**:
   - Uses current directory as primary
   - Uses `/home/ubuntu/DXB-events/DataCollection` as backup

2. **If current directory contains "DataCollection"**:
   - Uses current directory as primary  
   - Uses `/home/ubuntu/mydscvr-datacollection` as backup

3. **If run from elsewhere**:
   - Defaults to `/home/ubuntu/mydscvr-datacollection` as primary
   - Uses `/home/ubuntu/DXB-events/DataCollection` as backup

### Why This Design?
- **Flexibility**: Works regardless of where you run it
- **Redundancy**: Always has a backup source for missing files
- **Portability**: Can be copied to any server setup
- **Auto-repair**: Automatically fixes missing dependencies/files

## 🚀 Deployment Instructions

### Step 1: Copy Scripts to Server
```bash
# From your local machine
scp Backend/setup_permanent_dependencies.sh ubuntu@3.29.102.4:/home/ubuntu/mydscvr-datacollection/
scp Backend/cron_health_monitor.sh ubuntu@3.29.102.4:/home/ubuntu/mydscvr-datacollection/

# Make them executable
ssh ubuntu@3.29.102.4 "chmod +x /home/ubuntu/mydscvr-datacollection/*.sh"
```

### Step 2: Test the Setup
```bash
# SSH to server and test
ssh ubuntu@3.29.102.4
cd /home/ubuntu/mydscvr-datacollection
./setup_permanent_dependencies.sh
./cron_health_monitor.sh
```

### Step 3: Update Crontab
```bash
# Edit crontab on server
crontab -e

# Add these lines:
59 23 * * * cd /home/ubuntu/mydscvr-datacollection && ./cron_health_monitor.sh >> logs/health_cron.log 2>&1
0 0 * * * cd /home/ubuntu/mydscvr-datacollection && ./run_collection_with_ai.sh >> logs/cron_output.log 2>&1
```

## ⚡ Quick Recovery Procedures

### If Dependencies Go Missing Again:
```bash
# 1. Connect to server
ssh -i mydscvrkey.pem ubuntu@3.29.102.4

# 2. Run portable setup script
cd /home/ubuntu/mydscvr-datacollection
./setup_permanent_dependencies.sh

# 3. Test the fix
./run_collection_with_ai.sh
```

### If Scripts Are Missing:
```bash
# Re-copy from local Backend directory
scp Backend/*.sh ubuntu@3.29.102.4:/home/ubuntu/mydscvr-datacollection/
ssh ubuntu@3.29.102.4 "chmod +x /home/ubuntu/mydscvr-datacollection/*.sh"
```

## 📊 Monitoring Dashboard

### Key Log Files to Monitor:
- **Health Monitor**: `/home/ubuntu/mydscvr-datacollection/logs/health_monitor.log`
- **Cron Output**: `/home/ubuntu/mydscvr-datacollection/logs/cron_output.log`
- **Collection Process**: `/home/ubuntu/mydscvr-datacollection/logs/enhanced_collection.log`
- **System Cron**: `/var/log/syslog` (system-level execution)

### Success Indicators:
```bash
# Check if health monitor passed
tail -5 /home/ubuntu/mydscvr-datacollection/logs/health_monitor.log | grep "All health checks passed"

# Check if collection ran successfully
tail -10 /home/ubuntu/mydscvr-datacollection/logs/cron_output.log | grep -E "(Completed|Success)"
```

## 🔄 Regular Maintenance

### Weekly (Automated via Cron):
- ✅ Health checks run automatically before each collection
- ✅ Dependencies verified and auto-repaired
- ✅ Configuration files synced from backup

### Monthly (Manual):
```bash
# Update dependencies and create new snapshot
cd /home/ubuntu/mydscvr-datacollection
./setup_permanent_dependencies.sh
```

### Emergency Recovery:
```bash
# Nuclear option - complete rebuild
rm -rf venv
./setup_permanent_dependencies.sh
```

---

## ✅ Current Status (Post-Fix)

✅ **Scripts**: Portable and environment-aware  
✅ **Dependencies**: All installed and tested
✅ **Health Monitoring**: Automated pre-flight checks
✅ **Backup System**: Redundant environments ready
✅ **Documentation**: Complete troubleshooting guide

**Next Collection**: Will run at 1AM UTC tomorrow with full health verification first 