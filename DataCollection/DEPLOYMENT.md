# 🚀 DataCollection Deployment Guide

*Testing CI/CD pipeline after YAML syntax fixes*

## GitHub Secrets Configuration

All secrets are configured in the GitHub repository for secure deployment.

### Required GitHub Secrets

The following 13 secrets are configured:

- `MONGO_URI` - MongoDB Atlas connection string
- `MONGO_USER` - MongoDB username
- `MONGO_PASSWORD` - MongoDB password
- `MONGO_DB_NAME` - Database name (DXB)
- `FIRECRAWL_API_KEY` - Firecrawl API credentials
- `PERPLEXITY_API_KEY` - Perplexity AI API key
- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `BACKEND_API_KEY` - Backend API authentication key
- `SSH_PRIVATE_KEY` - SSH private key for server access
- `SERVER_HOST` - Production server IP address
- `SERVER_USER` - SSH username for deployment
- `DATACOLLECTION_USER` - DataCollection service user
- `DATACOLLECTION_PATH` - Installation path on server

## Deployment Process

### Automatic Deployment
- Push to `main` branch triggers automatic deployment
- GitHub Actions creates environment file from secrets
- Code deployed to production server
- Dependencies updated automatically
- Configuration tested post-deployment

### Manual Deployment
```bash
# Trigger manual deployment
gh workflow run deploy-datacollection.yml
```

## Collection Schedule

- **1:00 AM UTC** - Primary event collection (88 queries)
- **1:15 AM UTC** - Hidden gems generation
- **3:00 AM UTC** - Data deduplication  
- **3:15 PM UTC** - Afternoon refresh collection

## Security Features

✅ **All secrets stored in GitHub Secrets**  
✅ **No hardcoded credentials in code**  
✅ **Environment file excluded from git**  
✅ **Automated secure deployment**  
✅ **SSH key-based server access**

## Local Development

1. Copy template: `cp DataCollection.env.example DataCollection.env`
2. Fill in your development values
3. Never commit the actual `DataCollection.env` file

## Monitoring

- Collection logs available at: `/home/ubuntu/DXB-events/DataCollection/logs/`
- Cron job status: `crontab -l` on production server
- MongoDB data: Check Atlas dashboard for event counts

---

**Secure, automated, and production-ready!** 🔐