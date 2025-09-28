#!/usr/bin/env python3
"""
Simple Database Solution for Railway Volume Sharing
Minimale Änderung - ersetzt nur load_json_file und save_json_file
"""

import os
import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection - PostgreSQL or SQLite fallback"""
    database_url = os.getenv("DATABASE_URL")

    # Try PostgreSQL first
    if database_url and database_url.startswith("postgres"):
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            return conn, "postgres"
        except ImportError:
            logger.warning("psycopg2 not installed, falling back to SQLite")
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}, falling back to SQLite")

    # Fallback to SQLite
    data_dir = os.getenv("DATA_DIR", ".")
    db_path = os.path.join(data_dir, "biggie.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return conn, "sqlite"

def load_json_from_db(table_name):
    """Load JSON data from database table"""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()

        # Create table if not exists first (CRITICAL FIX)
        if db_type == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS json_storage (
                    table_name VARCHAR(50) PRIMARY KEY,
                    json_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
        else:  # sqlite
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS json_storage (
                    table_name TEXT PRIMARY KEY,
                    json_data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

        # Simple key-value storage für JSON files
        if db_type == "postgres":
            cursor.execute("SELECT json_data FROM json_storage WHERE table_name = %s", (table_name,))
        else:  # sqlite
            cursor.execute("SELECT json_data FROM json_storage WHERE table_name = ?", (table_name,))

        result = cursor.fetchone()
        conn.close()

        if result:
            # FIX: Handle both string and dict returns from PostgreSQL
            data = result[0]
            if isinstance(data, dict):
                return data  # Already parsed by PostgreSQL JSONB
            elif isinstance(data, str):
                return json.loads(data)  # Parse JSON string
            else:
                # Handle other types (bytes, etc.)
                return json.loads(str(data))
        return {}

    except Exception as e:
        logger.error(f"Database load error for {table_name}: {e}")
        return {}

def save_json_to_db(table_name, data):
    """Save JSON data to database table"""
    try:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()

        # Create table if not exists (compatible with both PostgreSQL and SQLite)
        if db_type == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS json_storage (
                    table_name VARCHAR(50) PRIMARY KEY,
                    json_data JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
        else:  # sqlite
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS json_storage (
                    table_name TEXT PRIMARY KEY,
                    json_data TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # Upsert operation (compatible syntax)
        if db_type == "postgres":
            # FIX: Pass data as dict, not JSON string for JSONB
            cursor.execute("""
                INSERT INTO json_storage (table_name, json_data)
                VALUES (%s, %s)
                ON CONFLICT (table_name)
                DO UPDATE SET
                    json_data = EXCLUDED.json_data,
                    updated_at = NOW()
            """, (table_name, json.dumps(data)))  # Still use json.dumps for consistency
        else:  # sqlite
            cursor.execute("""
                INSERT INTO json_storage (table_name, json_data)
                VALUES (?, ?)
                ON CONFLICT (table_name)
                DO UPDATE SET
                    json_data = excluded.json_data,
                    updated_at = CURRENT_TIMESTAMP
            """, (table_name, json.dumps(data)))

        conn.commit()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Database save error for {table_name}: {e}")
        return False

def load_json_file(file_path):
    """
    Load JSON - Database version with file fallback
    SICHERE MIGRATION: Funktioniert mit oder ohne Database
    """
    # Check if we have database connection
    if os.getenv("DATABASE_URL"):
        # Extract table name from file path
        table_name = os.path.basename(file_path).replace('.json', '')
        logger.info(f"Loading {table_name} from database")
        return load_json_from_db(table_name)
    else:
        # Fallback to original file system logic
        logger.info(f"Loading from file: {file_path}")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
                return {}
        return {}

def save_json_file(file_path, data):
    """
    Save JSON - Database version with file fallback
    SICHERE MIGRATION: Funktioniert mit oder ohne Database
    """
    # Check if we have database connection
    if os.getenv("DATABASE_URL"):
        # Extract table name from file path
        table_name = os.path.basename(file_path).replace('.json', '')
        logger.info(f"Saving {table_name} to database")
        return save_json_to_db(table_name, data)
    else:
        # Fallback to original file system logic
        logger.info(f"Saving to file: {file_path}")
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving {file_path}: {e}")
            return False

def migrate_files_to_database():
    """
    One-time migration script to move existing JSON files to database
    Run this once after setting up PostgreSQL
    """
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL not found - cannot migrate")
        return

    # Data directory
    data_dir = os.getenv("DATA_DIR", ".")

    # Files to migrate
    files_to_migrate = [
        "config.json",
        "user_data.json",
        "whitelist.json",
        "pending_whitelist.json",
        "rejected_groups.json",
        "verification_links.json"
    ]

    print("🔄 Starting migration from files to database...")

    for filename in files_to_migrate:
        file_path = os.path.join(data_dir, filename)

        if os.path.exists(file_path):
            print(f"📁 Migrating {filename}...")

            # Load from file
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                # Save to database
                table_name = filename.replace('.json', '')
                if save_json_to_db(table_name, data):
                    print(f"✅ {filename} migrated successfully")
                else:
                    print(f"❌ Failed to migrate {filename}")

            except Exception as e:
                print(f"❌ Error migrating {filename}: {e}")
        else:
            print(f"⏭️ {filename} not found, skipping")

    print("✅ Migration completed!")

if __name__ == "__main__":
    # Run migration if called directly
    migrate_files_to_database()

"""
DEPLOYMENT INSTRUCTIONS:

1. Add PostgreSQL service to Railway project

2. Add environment variable to BOTH services:
   DATABASE_URL=${{Postgres.DATABASE_URL}}

3. Replace imports in verification.py:
   # Change this:
   def load_json_file(file_path):
       # existing code...

   def save_json_file(file_path, data):
       # existing code...

   # To this:
   from database_simple import load_json_file, save_json_file

4. Add to requirements.txt:
   psycopg2-binary

5. Run migration (one time):
   python3 database_simple.py

6. Deploy both services

7. Set cron schedule for verify_cron service:
   0 */6 * * *

BENEFITS:
✅ Both services share same data via PostgreSQL
✅ Cron runs only when needed (cost-efficient)
✅ Minimal code changes (only 2 functions replaced)
✅ Safe fallback to files if database unavailable
✅ Railway-native solution
"""