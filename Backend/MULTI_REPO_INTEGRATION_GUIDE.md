# Multi-Repository Integration Guide

## 🏗️ Current Architecture

Your system has two separate repositories with CI/CD:

```
📁 mydscvr.backend
├── utils/                    # ← Shared utilities
├── models/
├── routers/
└── Backend API code

📁 mydscvr.datacollection  
├── enhanced_collection.py   # ← Needs utils/
├── run_collection_with_ai.sh
└── Data collection code
```

**Problem**: Datacollection needs `utils/` from backend, but they're separate repos.

## 🎯 Solution Options (Ranked by Recommendation)

### **Option 1: GitHub Actions Auto-Sync (RECOMMENDED)**

**How it works**: GitHub Actions automatically syncs `utils/` from backend to datacollection

**Pros**:
- ✅ Fully automated
- ✅ Triggered by backend changes
- ✅ Maintains repo separation
- ✅ Works with existing CI/CD

**Setup**:
1. Add `github_actions_utils_sync.yml` to `mydscvr.datacollection/.github/workflows/`
2. Configure GitHub secrets if backend is private
3. Backend changes automatically update datacollection

**Example Flow**:
```
Backend updated → GitHub Action → Sync utils → Commit to datacollection → Deploy
```

---

### **Option 2: Server-Side Sync Script**

**How it works**: Script on server syncs utils between deployed repos

**Pros**:
- ✅ Simple to implement
- ✅ Works with current setup
- ✅ Can run on schedule

**Setup**:
```bash
# Copy sync script to server
scp Backend/sync_utils_to_datacollection.sh ubuntu@server:/home/ubuntu/

# Add to cron (runs before each collection)
59 23 * * * /home/ubuntu/sync_utils_to_datacollection.sh >> /home/ubuntu/logs/utils_sync.log 2>&1
0 0 * * * cd /home/ubuntu/mydscvr-datacollection && ./run_collection_with_ai.sh
```

---

### **Option 3: Git Submodules**

**How it works**: Make backend a submodule of datacollection

**Pros**:
- ✅ Version-controlled dependencies
- ✅ Git-native solution
- ✅ Clean architecture

**Cons**:
- ❌ More complex git operations
- ❌ Requires learning submodules

**Setup**:
```bash
# In datacollection repo
git submodule add https://github.com/saleemjadallah/mydscvr.backend.git backend
# Access utils via: backend/utils/
```

---

### **Option 4: Python Package (Future-Proof)**

**How it works**: Publish utils as Python package

**Pros**:
- ✅ Industry standard
- ✅ Version management
- ✅ Clean imports

**Cons**:
- ❌ More initial setup
- ❌ Need package registry

**Setup**:
```python
# In backend repo, create setup.py
# Publish to PyPI or private registry
# In datacollection: pip install mydscvr-utils==1.0.0
```

## 🚀 Recommended Implementation: Option 1 + Option 2

**Hybrid Approach** (Best of both worlds):

1. **GitHub Actions** for development and CI/CD automation
2. **Server sync script** as backup/manual override

### **Step 1: GitHub Actions Setup**

```bash
# 1. Add workflow to datacollection repo
cp Backend/github_actions_utils_sync.yml /path/to/mydscvr.datacollection/.github/workflows/

# 2. Push to enable automation
cd /path/to/mydscvr.datacollection
git add .github/workflows/github_actions_utils_sync.yml
git commit -m "Add automated utils sync from backend"
git push
```

### **Step 2: Server Backup Script**

```bash
# Copy sync script to server
scp Backend/sync_utils_to_datacollection.sh ubuntu@3.29.102.4:/home/ubuntu/mydscvr-datacollection/
ssh ubuntu@3.29.102.4 "chmod +x /home/ubuntu/mydscvr-datacollection/sync_utils_to_datacollection.sh"

# Test the sync
ssh ubuntu@3.29.102.4 "cd /home/ubuntu/mydscvr-datacollection && ./sync_utils_to_datacollection.sh"
```

### **Step 3: Update Cron Job**

```bash
# Enhanced cron job with utils sync
0 0 * * * cd /home/ubuntu/mydscvr-datacollection && ./sync_utils_to_datacollection.sh >> logs/utils_sync.log 2>&1 && ./run_collection_with_ai.sh >> logs/cron_output.log 2>&1
```

## 📊 Comparison Matrix

| Solution | Setup Complexity | Automation | Maintenance | Reliability |
|----------|------------------|------------|-------------|-------------|
| GitHub Actions | Medium | High | Low | High |
| Server Sync | Low | Medium | Medium | Medium |
| Git Submodules | High | High | Low | High |
| Python Package | High | High | Low | Very High |

## 🔄 Workflow Examples

### **Development Workflow** (GitHub Actions):
```
1. Update utils in backend repo → Push
2. GitHub Action automatically syncs to datacollection
3. Datacollection auto-deploys with latest utils
4. Cron job runs with current utils
```

### **Emergency Workflow** (Server Sync):
```
1. SSH to server
2. Run manual sync: ./sync_utils_to_datacollection.sh
3. Verify: ./run_collection_with_ai.sh
```

## 🛠️ Current Status & Next Steps

### **Immediate Actions** (Choose One):

**For GitHub Actions approach**:
```bash
# Add workflow file to datacollection repo
# Enable automatic syncing
```

**For Server Sync approach**:
```bash
# Deploy sync script to server
# Update cron job to include sync
```

### **Long-term Strategy**:
1. **Short-term**: Use server sync for immediate reliability
2. **Medium-term**: Implement GitHub Actions for automation  
3. **Long-term**: Consider Python package for scalability

## ✅ Success Criteria

Your integration is successful when:
- ✅ Datacollection always has latest utils
- ✅ Cron jobs never fail due to missing dependencies
- ✅ Backend updates automatically propagate
- ✅ Manual override available for emergencies
- ✅ Clear logs for troubleshooting

**Current Priority**: Fix the immediate cron job dependency issue, then implement automated syncing for future reliability. 