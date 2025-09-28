#!/usr/bin/env python3
"""
Railway Database Connection Diagnostic Tool
This will help identify where each service is reading/writing data
"""

import os
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnose_data_storage():
    """Diagnose where data is being stored and read from"""

    print("🔍 RAILWAY DATABASE DIAGNOSTIC")
    print("="*50)

    # Check environment variables
    print("\n📊 ENVIRONMENT VARIABLES:")
    database_url = os.getenv("DATABASE_URL")
    data_dir = os.getenv("DATA_DIR", ".")

    print(f"DATABASE_URL: {'✅ SET' if database_url else '❌ NOT SET'}")
    if database_url:
        # Mask sensitive parts
        masked_url = database_url[:20] + "***" + database_url[-20:] if len(database_url) > 40 else "***"
        print(f"DATABASE_URL (masked): {masked_url}")

    print(f"DATA_DIR: {data_dir}")
    print(f"Current working directory: {os.getcwd()}")

    # Check if database connection works
    print("\n🔌 DATABASE CONNECTION TEST:")
    if database_url:
        try:
            from database_simple import get_db_connection
            conn, db_type = get_db_connection()
            print(f"✅ Database connection successful: {db_type}")
            conn.close()
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
    else:
        print("❌ No DATABASE_URL - using file system")

    # Test data loading
    print("\n📁 DATA LOADING TEST:")

    # Test config loading
    config_path = os.path.join(data_dir, "config.json")

    if database_url:
        print("Using DATABASE storage method...")
        try:
            from database_simple import load_json_file
            config = load_json_file(config_path)
            print(f"✅ Config loaded from database: {len(config)} groups found")

            for group_id, group_config in config.items():
                min_balance = group_config.get("min_balance", "NOT SET")
                token = group_config.get("token", "NOT SET")
                print(f"  Group {group_id}: min_balance={min_balance}, token={token[:10]}...")

        except Exception as e:
            print(f"❌ Database config load failed: {e}")

    # Also test file system
    print("\nUsing FILE SYSTEM method...")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
            print(f"✅ Config loaded from file: {len(file_config)} groups found")

            for group_id, group_config in file_config.items():
                min_balance = group_config.get("min_balance", "NOT SET")
                token = group_config.get("token", "NOT SET")
                print(f"  Group {group_id}: min_balance={min_balance}, token={token[:10]}...")

        except Exception as e:
            print(f"❌ File config load failed: {e}")
    else:
        print(f"❌ Config file does not exist: {config_path}")

    # Check if both methods return same data
    print("\n⚖️ DATA CONSISTENCY CHECK:")
    if database_url and os.path.exists(config_path):
        try:
            from database_simple import load_json_file as db_load
            with open(config_path, "r") as f:
                file_data = json.load(f)
            db_data = db_load(config_path)

            if file_data == db_data:
                print("✅ File and database data are IDENTICAL")
            else:
                print("❌ File and database data are DIFFERENT!")
                print("Database data:")
                print(json.dumps(db_data, indent=2)[:500])
                print("\nFile data:")
                print(json.dumps(file_data, indent=2)[:500])
        except Exception as e:
            print(f"❌ Consistency check failed: {e}")

    print("\n🎯 RECOMMENDATION:")
    if not database_url:
        print("❌ DATABASE_URL not set - services are using separate file systems")
        print("🔧 FIX: Set DATABASE_URL=${{Postgres.DATABASE_URL}} on BOTH services")
    elif database_url:
        print("✅ DATABASE_URL is set - services should share data")
        print("🔧 Check if both services have the same DATABASE_URL value")

if __name__ == "__main__":
    diagnose_data_storage()