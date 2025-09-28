# Railway 2025 Shared Data Solution for Biggie Bot

## 🚨 **Problem Identified**

Railway 2025 **DOES NOT support shared volumes between services**. Your customer is experiencing this issue:

```
2025-09-23 16:22:29,870 - __main__ - INFO - No groups configured for verification
```

## 🔍 **Research Findings**

### **Railway Volume Limitations (2025):**
- ❌ **No shared volumes between services**
- ❌ **No volume mounting on multiple services**
- ❌ **No docker-compose style shared volumes**
- ✅ **Each service gets its own isolated volume**

### **Official Railway Statement:**
> "Unfortunately you can't add two volumes to the same service or have a shared volume between 2 services"

## ✅ **SOLUTION: Use PostgreSQL Database Instead**

Railway **DOES** support shared databases between services. This is the recommended approach for 2025:

### **Why PostgreSQL Instead of JSON Files:**
1. **Shared Access** - Multiple services can connect to the same database
2. **Railway Native** - Built-in support with reference variables
3. **Persistent** - Data survives deployments and restarts
4. **Scalable** - Better performance than file-based storage

## 🚀 **Implementation Plan**

### **Step 1: Add PostgreSQL Service**
1. In Railway dashboard, click "Add Service"
2. Select "PostgreSQL" from templates
3. Railway will create a PostgreSQL service with connection variables

### **Step 2: Update Both Services**
Both the main bot and cron service will use the same PostgreSQL database:
- `DATABASE_URL` environment variable is shared
- Both services connect to the same database
- Data is instantly available to both services

### **Step 3: Update Code**
Replace JSON file storage with SQLite/PostgreSQL database operations.

## 📋 **Required Code Changes**

### **Database Schema:**
```sql
-- Groups configuration
CREATE TABLE groups (
    group_id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    token TEXT NOT NULL,
    min_balance REAL NOT NULL,
    verifier TEXT NOT NULL
);

-- User verification data
CREATE TABLE user_data (
    group_id TEXT,
    user_id TEXT,
    address TEXT,
    verified BOOLEAN,
    last_verified INTEGER,
    verification_tx BOOLEAN,
    PRIMARY KEY (group_id, user_id)
);

-- Whitelist
CREATE TABLE whitelist (
    group_id TEXT PRIMARY KEY,
    whitelisted BOOLEAN DEFAULT TRUE
);

-- Pending whitelist
CREATE TABLE pending_whitelist (
    group_id TEXT PRIMARY KEY,
    group_name TEXT,
    admin_id TEXT,
    admin_name TEXT,
    timestamp INTEGER
);

-- Rejected groups (3-strike system)
CREATE TABLE rejected_groups (
    group_id TEXT PRIMARY KEY,
    rejection_count INTEGER DEFAULT 0,
    group_name TEXT,
    last_admin_id TEXT,
    last_admin_name TEXT,
    first_rejection INTEGER,
    last_rejection INTEGER,
    blocked BOOLEAN DEFAULT FALSE
);

-- Verification links
CREATE TABLE verification_links (
    token TEXT PRIMARY KEY,
    group_id TEXT,
    created_at INTEGER
);
```

### **Environment Variables for Both Services:**
```bash
DATABASE_URL=${{Postgres.DATABASE_URL}}
TELEGRAM_BOT_TOKEN=your_bot_token
MORALIS_API_KEY=your_moralis_key
ETHERSCAN_API_KEY=your_etherscan_key
ADMIN_USER_ID=your_admin_id
```

## 🔧 **Migration Strategy**

### **Option 1: Database Adapter (Recommended)**
Create a database adapter that mimics the current JSON file interface:

```python
# database.py
import sqlite3
import os
import json

DATABASE_URL = os.getenv("DATABASE_URL")

class DatabaseAdapter:
    def load_json_file(self, table_name):
        """Load data from database table, return as dict like JSON files"""
        # Implementation connects to PostgreSQL/SQLite
        pass

    def save_json_file(self, table_name, data):
        """Save dict data to database table"""
        # Implementation connects to PostgreSQL/SQLite
        pass
```

### **Option 2: Quick SQLite Solution**
If PostgreSQL is too complex, use SQLite with a shared network storage solution:

1. Use Railway's PostgreSQL just for file storage
2. Store SQLite database as a blob in PostgreSQL
3. Both services download/upload the SQLite file

## 🎯 **Immediate Action Items**

### **For Customer:**
1. **Add PostgreSQL service** to Railway project
2. **Set DATABASE_URL** environment variable for both services
3. **Deploy updated code** with database support

### **For Development:**
1. **Create database adapter** to replace JSON file operations
2. **Update verification.py** to use database instead of files
3. **Test that both services** can read/write to shared database
4. **Migration script** to convert existing JSON data to database

## 📞 **Alternative Workarounds**

If database migration is too complex:

### **Option A: Single Service Architecture**
- Combine main bot and cron into one service
- Use internal job scheduling instead of Railway cron
- Eliminates need for shared data

### **Option B: API Communication**
- Main service exposes internal API
- Cron service calls main service API for data
- Both services stay separate but communicate

### **Option C: External Storage**
- Use external service like Supabase, PlanetScale, or AWS RDS
- Both Railway services connect to external database
- More complex but definitely works

## ✅ **Recommended Next Steps**

1. **Implement PostgreSQL solution** (most Railway-native)
2. **Create database migration script**
3. **Update both services** to use shared database
4. **Test shared data access** between services
5. **Deploy and verify** cron job sees configured groups

This approach will solve the volume sharing issue and make the bot more scalable! 🎉