#!/usr/bin/env python3
"""
Database Adapter for Railway PostgreSQL/SQLite
Replaces JSON file storage with database operations while maintaining the same interface
"""

import os
import json
import logging
import sqlite3
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DatabaseAdapter:
    """Database adapter that mimics JSON file interface"""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize database connection"""
        self.database_url = database_url or os.getenv("DATABASE_URL")
        self.is_postgres = self.database_url and self.database_url.startswith("postgres")

        if self.is_postgres:
            try:
                import psycopg2
                self.connection = psycopg2.connect(self.database_url)
                logger.info("✅ Connected to PostgreSQL database")
            except ImportError:
                logger.error("❌ psycopg2 not installed. Install with: pip install psycopg2-binary")
                self._fallback_to_sqlite()
            except Exception as e:
                logger.error(f"❌ PostgreSQL connection failed: {e}")
                self._fallback_to_sqlite()
        else:
            self._fallback_to_sqlite()

        self._create_tables()

    def _fallback_to_sqlite(self):
        """Fallback to SQLite if PostgreSQL is not available"""
        data_dir = os.getenv("DATA_DIR", ".")
        db_path = os.path.join(data_dir, "biggie.db")
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.is_postgres = False
        logger.info(f"✅ Connected to SQLite database: {db_path}")

    def _create_tables(self):
        """Create all required tables"""
        cursor = self.connection.cursor()

        # Groups configuration table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                group_id TEXT PRIMARY KEY,
                chain_id TEXT NOT NULL,
                token TEXT NOT NULL,
                min_balance REAL NOT NULL,
                verifier TEXT NOT NULL
            )
        """)

        # User verification data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_data (
                group_id TEXT,
                user_id TEXT,
                address TEXT,
                verified BOOLEAN,
                last_verified INTEGER,
                verification_tx BOOLEAN,
                PRIMARY KEY (group_id, user_id)
            )
        """)

        # Whitelist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                group_id TEXT PRIMARY KEY,
                whitelisted BOOLEAN DEFAULT TRUE
            )
        """)

        # Pending whitelist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_whitelist (
                group_id TEXT PRIMARY KEY,
                group_name TEXT,
                admin_id TEXT,
                admin_name TEXT,
                timestamp INTEGER
            )
        """)

        # Rejected groups table (3-strike system)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejected_groups (
                group_id TEXT PRIMARY KEY,
                rejection_count INTEGER DEFAULT 0,
                group_name TEXT,
                last_admin_id TEXT,
                last_admin_name TEXT,
                first_rejection INTEGER,
                last_rejection INTEGER,
                blocked BOOLEAN DEFAULT FALSE
            )
        """)

        # Verification links table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_links (
                token TEXT PRIMARY KEY,
                group_id TEXT,
                created_at INTEGER
            )
        """)

        self.connection.commit()
        logger.info("✅ Database tables created/verified")

    def load_config(self) -> Dict[str, Any]:
        """Load groups configuration (replaces config.json)"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT group_id, chain_id, token, min_balance, verifier FROM groups")

        config = {}
        for row in cursor.fetchall():
            group_id, chain_id, token, min_balance, verifier = row
            config[group_id] = {
                "chain_id": chain_id,
                "token": token,
                "min_balance": min_balance,
                "verifier": verifier
            }

        return config

    def save_config(self, config: Dict[str, Any]) -> bool:
        """Save groups configuration (replaces config.json)"""
        try:
            cursor = self.connection.cursor()

            # Clear existing config
            cursor.execute("DELETE FROM groups")

            # Insert new config
            for group_id, group_config in config.items():
                cursor.execute("""
                    INSERT INTO groups (group_id, chain_id, token, min_balance, verifier)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    group_id,
                    group_config["chain_id"],
                    group_config["token"],
                    group_config["min_balance"],
                    group_config["verifier"]
                ))

            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def load_user_data(self) -> Dict[str, Any]:
        """Load user verification data (replaces user_data.json)"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT group_id, user_id, address, verified, last_verified, verification_tx
            FROM user_data
        """)

        user_data = {}
        for row in cursor.fetchall():
            group_id, user_id, address, verified, last_verified, verification_tx = row

            if group_id not in user_data:
                user_data[group_id] = {}

            user_data[group_id][user_id] = {
                "address": address,
                "verified": bool(verified),
                "last_verified": last_verified,
                "verification_tx": bool(verification_tx)
            }

        return user_data

    def save_user_data(self, user_data: Dict[str, Any]) -> bool:
        """Save user verification data (replaces user_data.json)"""
        try:
            cursor = self.connection.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM user_data")

            # Insert new data
            for group_id, users in user_data.items():
                for user_id, user_info in users.items():
                    cursor.execute("""
                        INSERT INTO user_data
                        (group_id, user_id, address, verified, last_verified, verification_tx)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        group_id,
                        user_id,
                        user_info.get("address"),
                        user_info.get("verified", False),
                        user_info.get("last_verified"),
                        user_info.get("verification_tx", False)
                    ))

            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving user data: {e}")
            return False

    def load_whitelist(self) -> Dict[str, Any]:
        """Load whitelist data (replaces whitelist.json)"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT group_id, whitelisted FROM whitelist")

        whitelist = {}
        for row in cursor.fetchall():
            group_id, whitelisted = row
            whitelist[group_id] = bool(whitelisted)

        return whitelist

    def save_whitelist(self, whitelist: Dict[str, Any]) -> bool:
        """Save whitelist data (replaces whitelist.json)"""
        try:
            cursor = self.connection.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM whitelist")

            # Insert new data
            for group_id, whitelisted in whitelist.items():
                cursor.execute("""
                    INSERT INTO whitelist (group_id, whitelisted)
                    VALUES (?, ?)
                """, (group_id, whitelisted))

            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving whitelist: {e}")
            return False

    def load_pending_whitelist(self) -> Dict[str, Any]:
        """Load pending whitelist data (replaces pending_whitelist.json)"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT group_id, group_name, admin_id, admin_name, timestamp
            FROM pending_whitelist
        """)

        pending = {}
        for row in cursor.fetchall():
            group_id, group_name, admin_id, admin_name, timestamp = row
            pending[group_id] = {
                "group_name": group_name,
                "admin_id": admin_id,
                "admin_name": admin_name,
                "timestamp": timestamp
            }

        return pending

    def save_pending_whitelist(self, pending: Dict[str, Any]) -> bool:
        """Save pending whitelist data (replaces pending_whitelist.json)"""
        try:
            cursor = self.connection.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM pending_whitelist")

            # Insert new data
            for group_id, pending_info in pending.items():
                cursor.execute("""
                    INSERT INTO pending_whitelist
                    (group_id, group_name, admin_id, admin_name, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    group_id,
                    pending_info.get("group_name"),
                    pending_info.get("admin_id"),
                    pending_info.get("admin_name"),
                    pending_info.get("timestamp")
                ))

            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving pending whitelist: {e}")
            return False

    def load_rejected_groups(self) -> Dict[str, Any]:
        """Load rejected groups data (replaces rejected_groups.json)"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT group_id, rejection_count, group_name, last_admin_id,
                   last_admin_name, first_rejection, last_rejection, blocked
            FROM rejected_groups
        """)

        rejected = {}
        for row in cursor.fetchall():
            (group_id, rejection_count, group_name, last_admin_id,
             last_admin_name, first_rejection, last_rejection, blocked) = row

            rejected[group_id] = {
                "rejection_count": rejection_count,
                "group_name": group_name,
                "last_admin_id": last_admin_id,
                "last_admin_name": last_admin_name,
                "first_rejection": first_rejection,
                "last_rejection": last_rejection,
                "blocked": bool(blocked)
            }

        return rejected

    def save_rejected_groups(self, rejected: Dict[str, Any]) -> bool:
        """Save rejected groups data (replaces rejected_groups.json)"""
        try:
            cursor = self.connection.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM rejected_groups")

            # Insert new data
            for group_id, rejected_info in rejected.items():
                cursor.execute("""
                    INSERT INTO rejected_groups
                    (group_id, rejection_count, group_name, last_admin_id,
                     last_admin_name, first_rejection, last_rejection, blocked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    group_id,
                    rejected_info.get("rejection_count", 0),
                    rejected_info.get("group_name"),
                    rejected_info.get("last_admin_id"),
                    rejected_info.get("last_admin_name"),
                    rejected_info.get("first_rejection"),
                    rejected_info.get("last_rejection"),
                    rejected_info.get("blocked", False)
                ))

            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving rejected groups: {e}")
            return False

    def load_verification_links(self) -> Dict[str, Any]:
        """Load verification links data (replaces verification_links.json)"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT token, group_id FROM verification_links")

        links = {}
        for row in cursor.fetchall():
            token, group_id = row
            links[token] = group_id

        return links

    def save_verification_links(self, links: Dict[str, Any]) -> bool:
        """Save verification links data (replaces verification_links.json)"""
        try:
            cursor = self.connection.cursor()

            # Clear existing data
            cursor.execute("DELETE FROM verification_links")

            # Insert new data
            for token, group_id in links.items():
                cursor.execute("""
                    INSERT INTO verification_links (token, group_id, created_at)
                    VALUES (?, ?, ?)
                """, (token, group_id, int(time.time())))

            self.connection.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving verification links: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("✅ Database connection closed")

# Global database instance
_db_adapter = None

def get_db_adapter() -> DatabaseAdapter:
    """Get or create global database adapter instance"""
    global _db_adapter
    if _db_adapter is None:
        _db_adapter = DatabaseAdapter()
    return _db_adapter

# JSON file compatibility functions
def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load data from database (replaces JSON file loading)"""
    db = get_db_adapter()

    # Map file paths to database methods
    if "config.json" in file_path:
        return db.load_config()
    elif "user_data.json" in file_path:
        return db.load_user_data()
    elif "whitelist.json" in file_path:
        return db.load_whitelist()
    elif "pending_whitelist.json" in file_path:
        return db.load_pending_whitelist()
    elif "rejected_groups.json" in file_path:
        return db.load_rejected_groups()
    elif "verification_links.json" in file_path:
        return db.load_verification_links()
    else:
        logger.warning(f"Unknown file path: {file_path}")
        return {}

def save_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    """Save data to database (replaces JSON file saving)"""
    db = get_db_adapter()

    # Map file paths to database methods
    if "config.json" in file_path:
        return db.save_config(data)
    elif "user_data.json" in file_path:
        return db.save_user_data(data)
    elif "whitelist.json" in file_path:
        return db.save_whitelist(data)
    elif "pending_whitelist.json" in file_path:
        return db.save_pending_whitelist(data)
    elif "rejected_groups.json" in file_path:
        return db.save_rejected_groups(data)
    elif "verification_links.json" in file_path:
        return db.save_verification_links(data)
    else:
        logger.warning(f"Unknown file path: {file_path}")
        return False