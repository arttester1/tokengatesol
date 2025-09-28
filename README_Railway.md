# Railway Deployment Guide - Biggie Telegram Bot

## ⚠️ CRITICAL: Common Setup Mistakes

**❌ DO NOT set start command to `python verify_cron.py`**
**✅ The main bot service should use `python3 main.py` (automatic via Procfile)**

**❌ DO NOT manually override the start command in Railway**
**✅ Let Railway use the Procfile automatically**

## Overview
This bot has been optimized for Railway deployment with proper persistent storage and scheduled verification.

## Step 1: Required Environment Variables

**CRITICAL**: Set these in Railway → Your Service → Variables tab:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
MORALIS_API_KEY=your_moralis_api_key
ETHERSCAN_API_KEY=your_etherscan_api_key
ADMIN_USER_ID=1825755152
DATA_DIR=/app/data
```

**⚠️ Bot will crash immediately if TELEGRAM_BOT_TOKEN is missing!**

## Railway Volume Configuration

1. **Create Volume**: In Railway dashboard, create a new Volume
2. **Mount Path**: Set mount path to `/app/data`
3. **Volume Size**: Start with 1GB (can be grown later)

This volume will persist:
- `config.json` - Group configurations
- `user_data.json` - Verified users data
- `verification_links.json` - Verification tokens
- `whitelist.json` - Whitelisted groups
- `pending_whitelist.json` - Pending approvals
- `invite_links.json` - Generated invite links
- `verified_users.json` - User verification status

## Cron Job Setup (Optional - for periodic verification)

### Option 1: Separate Cron Service (Recommended)
1. Create new Railway service
2. Use same repository/branch
3. Set start command: `python verify_cron.py`
4. Set cron schedule: `0 */6 * * *` (every 6 hours)
5. Mount same volume to `/app/data`
6. Set same environment variables

### Option 2: Manual Verification
Use the bot's `/test_verify` command (owner only) to manually trigger verification.

## Files Changed for Railway Compatibility

- `procfile` → `Procfile` (capitalization fixed)
- `requirements.txt` - removed deprecated `asyncio==3.4.3` and `pip==24.2`
- `railway.json` - added Railway configuration
- `main.py` - removed job queue, externalized config, fixed DATA_DIR
- `verify_cron.py` - new standalone cron script for periodic verification

## Important Notes

- **Volume Mount**: Data persists in `/app/data` via Railway Volume
- **No Job Queue**: Removed `run_repeating()` - incompatible with Railway
- **Cron Alternative**: Use Railway cron jobs for periodic verification
- **Worker Process**: Runs as `worker` type (not `web`) since it's a bot
- **Auto Restart**: Configured to restart on failure

## Testing

1. Bot should start successfully and show "Bot starting..." message
2. JSON files should be created in the mounted volume
3. All bot functions (setup, verification, etc.) should work normally
4. Data should persist across redeploys

## Troubleshooting: Empty Deploy Logs / Bot Not Responding

If you see **"No logs in this time range"** or bot doesn't respond:

### 1. Check Environment Variables
```bash
# Bot will show this on startup if configured correctly:
✅ Environment check passed:
- TELEGRAM_BOT_TOKEN: ✅ Set
- MORALIS_API_KEY: ✅ Set
- ETHERSCAN_API_KEY: ✅ Set
- DATA_DIR: /app/data
- ADMIN_USER_ID: 1825755152
```

### 2. Verify Start Command
- **Railway should automatically use**: `worker: python3 main.py` from Procfile
- **Do NOT manually set start command to**: `python verify_cron.py`
- **verify_cron.py is for a separate cron service only**

### 3. Check Service Type
- Main bot = **Worker service** (runs `main.py`)
- Verification = **Separate cron service** (runs `verify_cron.py`)

### 4. Volume Mount
- Create volume in Railway dashboard
- Mount to `/app/data`
- Bot will show: `DATA_DIR: /app/data`

## Support

If you encounter issues:
1. Check Railway logs for error messages
2. Verify all environment variables are set
3. Ensure volume is properly mounted
4. Check that the volume has sufficient space
5. Look for the environment check output in logs