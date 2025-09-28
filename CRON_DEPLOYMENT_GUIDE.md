# Railway Cron Deployment Guide - Auto Verification Fix

## 🔧 **Problem Fixed**
The issue was that `verify_cron.py` was importing from `main.py`, which caused the entire bot to start when the cron job ran instead of just running verification.

## ✅ **Solution Implemented**
1. **Created `verification.py`** - Extracted all verification functions into a separate module
2. **Updated `verify_cron.py`** - Now imports from `verification.py` (no bot startup)
3. **Updated `main.py`** - Now imports from `verification.py` (cleaner code)
4. **Created `railway-cron.json`** - Separate configuration for cron services

## 🚀 **Railway Deployment Instructions**

### **Step 1: Deploy Main Bot Service**
1. Use the existing service with `railway.json`
2. This runs `python3 main.py` continuously as a worker process

### **Step 2: Create Cron Service**
1. Create a **NEW** Railway service for cron jobs
2. Connect it to the same GitHub repository
3. **IMPORTANT**: Upload the `railway-cron.json` file
4. In Railway dashboard, rename `railway-cron.json` to `railway.json` for the cron service
5. Set the cron schedule: `0 */6 * * *` (every 6 hours)

### **Step 3: Environment Variables**
Make sure both services have the same environment variables:
- `TELEGRAM_BOT_TOKEN`
- `MORALIS_API_KEY`
- `ETHERSCAN_API_KEY`
- `ADMIN_USER_ID`
- `DATA_DIR` (if using Railway volumes)

## 📋 **File Structure**
```
main.py              # Main bot (imports from verification.py)
verify_cron.py       # Standalone cron script
verification.py      # Shared verification functions (NEW)
railway.json         # Main bot config: python3 main.py
railway-cron.json    # Cron config: python3 verify_cron.py
```

## 🔍 **How to Test**

### **Test Cron Script Locally:**
```bash
# This should NOT start the bot (no bot startup messages)
python3 verify_cron.py
```

### **Test Main Bot Locally:**
```bash
# This SHOULD start the bot normally
python3 main.py
```

## ⚙️ **Railway Cron Configuration Options**

### **Option 1: Two Services (Recommended)**
- **Service 1**: Main bot with `railway.json` → `python3 main.py`
- **Service 2**: Cron job with `railway-cron.json` → `python3 verify_cron.py`

### **Option 2: Single Service with Custom Cron**
If Railway allows custom start commands in cron:
- Set cron start command to: `python3 verify_cron.py`
- Keep main service running: `python3 main.py`

## 🎯 **Expected Behavior**

### **Main Bot Service:**
- Runs continuously
- Handles all Telegram interactions
- Processes setup, verification, admin commands
- Restarts automatically if it crashes

### **Cron Service:**
- Runs every 6 hours
- Only does periodic verification
- Removes users who no longer meet token requirements
- Exits after completion (no continuous running)

## 🐛 **Troubleshooting**

### **If Cron Still Runs Main Bot:**
1. Check that `verify_cron.py` imports from `verification.py`
2. Verify Railway is using `railway-cron.json` with correct start command
3. Check Railway logs - should see "Starting Railway cron verification job"

### **If Functions Are Missing:**
- All verification functions are now in `verification.py`
- Both `main.py` and `verify_cron.py` import from this module
- No functions should be duplicated

### **If Import Errors Occur:**
- Ensure `verification.py` is deployed to both services
- Check that all required dependencies are installed
- Verify file permissions and paths

## ✅ **Success Indicators**

### **Cron Working Correctly:**
- Railway cron logs show: "Starting Railway cron verification job"
- No bot startup messages in cron logs
- Verification completes and exits
- Users with insufficient tokens are removed

### **Main Bot Working Correctly:**
- Bot responds to commands normally
- Setup, admin, and verification flows work
- All imported functions work correctly
- No missing function errors