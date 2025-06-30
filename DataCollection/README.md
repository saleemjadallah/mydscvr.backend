# Dubai Events Data Collection - Perplexity AI System

> **Simplified, efficient event discovery for Dubai using Perplexity AI**

This system has been completely redesigned to use **Perplexity AI** as the sole data source, replacing the previous complex Firecrawl-based architecture with a streamlined approach.

## 🎯 What Changed (December 2024)

### ✅ **NEW: Perplexity-Only System**
- **Single API**: Uses only Perplexity AI for event discovery and extraction
- **Real-time web data**: Perplexity provides current, accurate event information
- **No scraping**: Eliminates the need for web scraping and anti-bot measures
- **Simplified architecture**: Much cleaner codebase and dependencies

### ❌ **REMOVED: Legacy Components**
- ~~Firecrawl~~ - No longer needed
- ~~Custom scrapers~~ - Replaced by Perplexity
- ~~Celery + Redis~~ - No background tasks needed
- ~~Complex rate limiting~~ - Simplified to Perplexity limits only
- ~~Multiple data sources~~ - Single reliable source

## 🚀 Quick Start

### 1. **Install Dependencies**
```bash
cd DataCollection
pip install -r requirements.txt
```

### 2. **Configure API Keys**
Ensure your `AI_API.env` file contains:
```bash
PERPLEXITY_API_KEY=your_perplexity_api_key_here
```

### 3. **Run Data Collection**

#### Test Mode (Quick validation)
```bash
python main.py collect --mode test
```

#### Quick Collection (Family + Entertainment)
```bash
python main.py collect --mode quick
```

#### Comprehensive Collection (All categories)
```bash
python main.py collect --mode comprehensive
```

#### Targeted Collection (Specific categories)
```bash
python main.py collect --mode targeted --categories family cultural entertainment
```

### 4. **Health Check**
```bash
python main.py health
```

### 5. **Database Status**
```bash
python main.py status
```

## 📊 Complete System Architecture

### **Full Stack Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Perplexity    │    │   Data Server    │    │    Backend      │    │    Frontend     │
│      AI API     │────│   (EC2 Server)   │────│     API         │────│   (Next.js)     │
│                 │    │                  │    │                 │    │                 │
│ • Real-time     │    │ • Data Collection│    │ • REST API      │    │ • User Interface│
│   web data      │    │ • Event          │    │ • Data filtering│    │ • Event display │
│ • Event         │    │   processing     │    │ • Family scoring│    │ • Search & filter│
│   extraction    │    │ • MongoDB storage│    │ • Caching       │    │ • Responsive UI │
│ • Structured    │    │ • Automation     │    │ • Rate limiting │    │ • Real-time     │
│   responses     │    │ • Monitoring     │    │ • Error handling│    │   updates       │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
       │                        │                        │                        │
       │                        │                        │                        │
   API Calls                MongoDB                  HTTP API                 Web App
  (Search &                 Database              (JSON Responses)          (User Access)
   Extract)                (Event Store)          (Event Queries)          (Event Viewing)
```

### **Component Details**

#### **1. Perplexity AI API** 🤖
- **Purpose**: Real-time event discovery and extraction
- **Location**: External service (api.perplexity.ai)
- **Features**: 
  - Web search with current data
  - Structured JSON responses
  - Natural language processing
  - High accuracy event extraction

#### **2. Data Server (EC2)** 🖥️
- **Purpose**: Automated data collection and processing
- **Location**: `ubuntu@3.29.102.4`
- **Path**: `/home/ubuntu/DataCollection/`
- **Features**:
  - Scheduled event collection
  - Data validation and enhancement
  - Family score calculation
  - Duplicate detection
  - MongoDB integration
  - Health monitoring

#### **3. Backend API** 🔧
- **Purpose**: Data service layer for frontend
- **Location**: `ubuntu@3.29.102.4` (Backend directory)
- **Features**:
  - REST API endpoints
  - Event filtering and sorting
  - Family-friendly categorization
  - Caching for performance
  - Rate limiting
  - Error handling

#### **4. Frontend (Next.js)** 🎨
- **Purpose**: User interface for event discovery
- **Features**:
  - Responsive design
  - Event search and filtering
  - Family-friendly indicators
  - Real-time updates
  - Category browsing
  - Interactive maps

### **Data Flow Process**
```
1. ⏰ SCHEDULED TRIGGER
   └── Data Server runs collection script
   
2. 🔍 EVENT DISCOVERY
   └── Perplexity AI searches for Dubai events
   
3. 📊 DATA PROCESSING
   ├── Extract structured event data
   ├── Validate and enhance information
   ├── Calculate family scores
   └── Remove duplicates
   
4. 💾 STORAGE
   └── Store events in MongoDB database
   
5. 🔌 API ACCESS
   └── Backend exposes events via REST API
   
6. 🌐 USER INTERFACE
   └── Frontend fetches and displays events
   
7. 👥 USER INTERACTION
   └── Users browse, search, and discover events
```

### **Network Architecture**
```
Internet Users
      │
      ▼
┌─────────────┐
│   CDN/DNS   │ (Frontend Distribution)
└─────────────┘
      │
      ▼
┌─────────────┐
│   Nginx     │ (Web Server)
│   Proxy     │
└─────────────┘
      │
      ▼
┌─────────────┐
│   Backend   │ (API Server)
│   (FastAPI) │ Port 8000
└─────────────┘
      │
      ▼
┌─────────────┐
│   MongoDB   │ (Database)
│   (Atlas)   │ Port 27017
└─────────────┘
      ▲
      │
┌─────────────┐
│   Data      │ (Collection Service)
│ Collection  │ Automated Scripts
└─────────────┘
      ▲
      │
┌─────────────┐
│ Perplexity  │ (External API)
│     AI      │ HTTPS Calls
└─────────────┘
```

### **Deployment Environment**
- **Server**: AWS EC2 (ubuntu@3.29.102.4)
- **Database**: MongoDB Atlas (Cloud)
- **External API**: Perplexity AI
- **Domain**: [Your domain here]
- **SSL**: HTTPS encryption
- **Monitoring**: Automated health checks

### **Integration Points**
1. **Perplexity ↔ Data Server**: HTTPS API calls for event extraction
2. **Data Server ↔ MongoDB**: Direct database connection for storage
3. **Backend ↔ MongoDB**: Database queries for event retrieval
4. **Frontend ↔ Backend**: REST API calls for event data
5. **Users ↔ Frontend**: HTTPS web interface for event browsing

### **Automation & Scheduling**
The system runs continuously with automated data collection:

```
┌─────────────────────────────────────────┐
│            Automation Schedule          │
├─────────────────────────────────────────┤
│ ⏰ Every 6 hours: Comprehensive scan    │
│ ⏰ Daily at 6 AM: Full category sweep   │
│ ⏰ Weekly: Deep archive cleanup         │
│ 🔍 Real-time: Health monitoring        │
│ 📧 Alerts: System notifications        │
└─────────────────────────────────────────┘
```

#### **Server Commands for Management**
```bash
# SSH into data server
ssh -i DataCollection/mydscvrkey.pem ubuntu@3.29.102.4

# Navigate to data collection
cd DataCollection && source venv/bin/activate

# Manual operations
python run_perplexity_collection.py --mode comprehensive  # Full scan
python run_perplexity_collection.py --mode status         # Check status
python run_perplexity_collection.py --mode test           # Quick test

# System health
python -c "from monitoring.logging_config import quick_health_check; print('✅ Healthy' if quick_health_check() else '❌ Issues')"
```

#### **Data Freshness**
- **New Events**: Discovered within 6 hours
- **Updates**: Event changes reflected same day
- **Cleanup**: Old/expired events removed weekly
- **Monitoring**: 24/7 system health checks

## 🎛️ Configuration

### **Main Settings**: `config/perplexity_settings.py`
- **Perplexity API Configuration**: Model, rate limits, timeout settings
- **Search Categories**: Predefined search queries for different event types
- **Data Quality**: Validation rules and family scoring weights
- **MongoDB Configuration**: Database and collection settings

### **Legacy Settings**: `config/settings.py` *(DEPRECATED)*
- Kept for backward compatibility only
- Issues deprecation warnings
- Will be removed in future version

## 📂 Project Structure

```
DataCollection/
├── main.py                          # 🆕 Main entry point with CLI
├── run_perplexity_collection.py     # 🆕 Core collection pipeline
├── perplexity_events_extractor.py   # 🆕 Perplexity API integration
├── perplexity_storage.py            # 🆕 MongoDB storage for events
├── config/
│   ├── perplexity_settings.py       # 🆕 Clean configuration
│   └── settings.py                  # ⚠️ DEPRECATED (backward compatibility)
├── monitoring/
│   └── logging_config.py            # 🆕 Simplified monitoring
├── logs/                            # System logs
├── AI_API.env                       # API keys
├── Mongo.env                        # Database connection
└── requirements.txt                 # 🆕 Simplified dependencies
```

## 🎯 Event Categories

The system automatically discovers events in these categories:

- **Family**: Kids activities, family-friendly events
- **Nightlife**: Bars, clubs, parties, concerts
- **Cultural**: Museums, art exhibitions, cultural events
- **Sports**: Fitness activities, sports events
- **Business**: Conferences, networking events
- **Dining**: Food festivals, restaurant events
- **Entertainment**: Shows, comedy, theater
- **Educational**: Workshops, classes, learning
- **Outdoor**: Beach activities, water sports
- **Shopping**: Markets, fashion events
- **Luxury**: VIP experiences, premium events

## 📈 Data Quality Features

### **Automatic Family Scoring**
Events receive a family score (0-100) based on:
- Age inclusivity (25%)
- Safety and supervision (20%)
- Educational value (15%)
- Duration appropriateness (15%)
- Venue accessibility (15%)
- Family-friendly pricing (10%)

### **Data Validation**
- Title and description length checks
- Date and time validation
- Venue information verification
- Duplicate detection
- Price range validation

### **Smart Categorization**
- Automatic event type detection
- Multi-category support
- Age appropriateness assessment

## 🔧 API Reference

### **Direct Script Usage**
```bash
# Health check
python main.py health

# Database status
python main.py status

# Test collection (few events)
python main.py collect --mode test

# Quick collection (family + entertainment)
python main.py collect --mode quick

# Full collection (all categories)
python main.py collect --mode comprehensive

# Targeted collection
python main.py collect --mode targeted --categories family cultural sports
```

### **Legacy Script Support**
```bash
# Still works but deprecated
python run_perplexity_collection.py --mode test
```

## 📊 Monitoring & Logging

### **Health Monitoring**
- **Perplexity API**: Connectivity and response time
- **MongoDB**: Database accessibility and performance
- **System Status**: Overall health assessment

### **Logging Levels**
- **Console**: INFO level with colors
- **File**: DEBUG level with rotation
- **Performance**: Response times and success rates

### **Log Files**
- `logs/main.log` - Main application logs
- `logs/perplexity_collection.log` - Collection pipeline logs
- `logs/perplexity_monitoring.log` - Health monitoring logs

## 🔄 Migration from Legacy System

### **If you were using the old system:**

1. **Update imports:**
   ```python
   # OLD
   from config.settings import get_settings
   
   # NEW
   from config.perplexity_settings import get_settings
   ```

2. **Update scripts:**
   ```bash
   # OLD
   python run_data_collection.py
   
   # NEW
   python main.py collect --mode comprehensive
   ```

3. **Remove unused files:**
   - Old Firecrawl scrapers are automatically removed
   - Legacy requirements are cleaned up
   - Deprecated configurations show warnings

## 🚨 Troubleshooting

### **Common Issues**

#### "Perplexity API key not configured"
```bash
# Check your AI_API.env file
cat AI_API.env | grep PERPLEXITY_API_KEY
```

#### "MongoDB connection failed"
```bash
# Test MongoDB connectivity
python main.py health
```

#### "JSON parse error from Perplexity"
- Usually resolves itself on retry
- Check if Perplexity API is experiencing issues
- Verify API key permissions

### **Performance Optimization**
- **Rate Limiting**: System automatically respects Perplexity rate limits
- **Batch Processing**: Events processed in optimal batches
- **Caching**: Duplicate detection prevents unnecessary API calls

## 📝 Change Log

### **v2.0.0 (December 2024)**
- ✅ Complete rewrite using Perplexity AI
- ✅ Removed Firecrawl dependency
- ✅ Simplified architecture
- ✅ New CLI interface
- ✅ Enhanced monitoring
- ✅ Better error handling

### **v1.x (Legacy)**
- ❌ Firecrawl-based scraping
- ❌ Complex multi-source approach
- ❌ Heavy dependencies
- ❌ Difficult maintenance

## 🤝 Contributing

1. This system is now much simpler to work with
2. All changes should maintain the Perplexity-only approach
3. Test with `python main.py collect --mode test` before committing
4. Update documentation for any configuration changes

## 📧 Support

For issues with the new system:
1. Run `python main.py health` to check system status
2. Check logs in the `logs/` directory
3. Verify API keys in `AI_API.env`
4. Ensure MongoDB connectivity

---

**🎉 The new system is much simpler, more reliable, and easier to maintain!**
