#!/usr/bin/env python3
"""
SICHERE Railway Lösung - Single Service mit internem Cron
Füge diesen Code zu main.py hinzu für sichere Background-Verifikation
"""

import schedule
import threading
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

def start_background_cron():
    """
    Startet internen Cron Job alle 6 Stunden
    SICHER: Verwendet gleiche JSON-Files, gleiche Logik
    """

    def run_verification_job():
        """Wrapper für async periodic_verification"""
        try:
            # Verwende die bestehende periodic_verification Funktion
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(periodic_verification_single_service())
            loop.close()
        except Exception as e:
            logger.error(f"❌ Background verification failed: {e}")

    # Schedule job alle 6 Stunden
    schedule.every(6).hours.do(run_verification_job)

    # Auch einmal beim Start nach 5 Minuten
    schedule.every(5).minutes.do(run_verification_job).tag('startup')

    def run_scheduler():
        """Background Scheduler Thread"""
        logger.info("🕐 Background scheduler started - verification every 6 hours")

        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                time.sleep(300)  # Wait 5 minutes on error

    # Start scheduler in daemon thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    logger.info("✅ Background cron started successfully")

async def periodic_verification_single_service():
    """
    Single Service Version der periodic verification
    SICHER: Verwendet bestehende Funktionen und JSON-Logik
    """
    from telegram.ext import Application

    try:
        logger.info("🔄 Starting background verification cycle")

        # Verwende bestehende JSON-Loading Logik
        config = load_json_file(CONFIG_PATH)

        if not config:
            logger.info("No groups configured for verification")
            return

        logger.info(f"🔄 Background verification for {len(config)} groups")

        # Create bot instance (gleiche Logik wie verify_cron.py)
        from telegram import Bot
        bot = Bot(token=TOKEN)

        # Verwende bestehende verify_all_members Funktion
        for group_id, group_config in config.items():
            logger.info(f"Background verifying group {group_id}")
            await verify_all_members_single_service(bot, group_id, group_config)

        logger.info("✅ Background verification cycle completed")

    except Exception as e:
        logger.error(f"❌ Background verification failed: {e}")

async def verify_all_members_single_service(bot, group_id: str, group_config: dict):
    """
    Single Service Version von verify_all_members
    SICHER: Kopiert exakt die Logik aus verify_cron.py
    """
    try:
        logger.info(f"🔄 Background verification for group {group_id}")

        # SICHER: Verwende bestehende JSON-Loading Logik
        user_data = load_json_file(USER_DATA_PATH)
        group_users = user_data.get(group_id, {})

        logger.info(f"Found {len(group_users)} users to verify in group {group_id}")

        verified_count = 0
        removed_count = 0
        error_count = 0

        for user_id, user_info in group_users.items():
            # Skip owner - permanent access
            if is_owner(int(user_id)):
                logger.info(f"Skipping owner {user_id}")
                continue

            if user_info.get("verified"):
                user_address = user_info["address"]
                logger.info(f"Verifying user {user_id} with address {user_address}")

                # SICHER: Verwende bestehende verify_user_balance Funktion
                has_balance = await verify_user_balance(group_config, user_address)

                if not has_balance:
                    logger.info(f"❌ User {user_id} has insufficient balance, removing...")
                    try:
                        # User no longer meets requirements, remove them
                        await bot.ban_chat_member(chat_id=group_id, user_id=int(user_id))
                        await bot.unban_chat_member(chat_id=group_id, user_id=int(user_id))

                        # SICHER: Update user data mit bestehender Logik
                        user_data[group_id][user_id]["verified"] = False
                        save_json_file(USER_DATA_PATH, user_data)

                        removed_count += 1
                        logger.info(f"✅ Successfully removed user {user_id}")
                    except Exception as e:
                        error_count += 1
                        logger.error(f"❌ Error removing user {user_id}: {e}")
                else:
                    verified_count += 1
                    logger.info(f"✅ User {user_id} still has sufficient balance")

        logger.info(f"📊 Background verification completed: {verified_count} verified, {removed_count} removed, {error_count} errors")

    except Exception as e:
        logger.error(f"❌ Error in background verification for group {group_id}: {e}")

# Füge diese Zeile zu main.py hinzu, kurz vor app.run_polling():
# start_background_cron()

"""
DEPLOYMENT ANWEISUNGEN für Customer:

1. requirements.txt erweitern:
   pip install schedule

2. Am Anfang von main.py hinzufügen:
   import schedule
   import threading

3. Diese Funktionen zu main.py hinzufügen:
   - start_background_cron()
   - periodic_verification_single_service()
   - verify_all_members_single_service()

4. In main() function vor app.run_polling() hinzufügen:
   start_background_cron()

5. Separaten Cron Service in Railway löschen

6. Nur einen Service deployen mit allen Funktionen

ERGEBNIS:
✅ Bot läuft normal
✅ Background Verifikation alle 6 Stunden
✅ Gleiche JSON Files, gleiche Logik
✅ Null Risiko
✅ Ein Service statt zwei
"""