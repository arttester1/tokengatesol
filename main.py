print("🔄 Starting imports...")
try:
    import logging
    import json
    import os
    import asyncio
    import re
    import pprint
    import secrets
    import time
    print("✅ Basic imports successful")

    from moralis import sol_api
    import aiohttp
    print("✅ API imports successful")

    from verify_cron import verify_all_members
    from datetime import datetime, timezone, timedelta
    from collections import deque
    from typing import Dict, Any
    print("✅ Utility imports successful")

    from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
    from telegram.ext import (
        Application,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
        CallbackContext,
        CallbackQueryHandler
    )
    print("✅ Telegram imports successful")

except ImportError as e:
    print(f"💥 IMPORT ERROR: {e}")
    print("📦 Missing dependency - check requirements.txt")
    exit(1)
except Exception as e:
    print(f"💥 UNEXPECTED IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("✅ All imports completed successfully")

# Import verification functions from verification module
from verification import (
    load_json_file, save_json_file, is_owner, get_token_from_env,
    track_rejection, is_group_blocked,
    get_rejection_count, reset_rejection_count, get_blocked_groups,
    get_all_rejections, is_group_whitelisted, whitelist_group,
    add_pending_whitelist, remove_pending_whitelist,
    CONFIG_PATH, USER_DATA_PATH, WHITELIST_PATH, PENDING_WHITELIST_PATH,
    REJECTED_GROUPS_PATH
)

# Import blockchain functions from blockchain_integrations module
from blockchain_integrations import (
    verify_user_balance, check_token_transfer_moralis, get_token_decimals,
    is_valid_ethereum_address, CHAIN_MAP, PUBLIC_RPC_ENDPOINTS,
    get_token_balance_moralis
)

# Get tokens and admin user ID
TOKEN, MORALIS_API_KEY, _ = get_token_from_env()
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "1825755152")

# Support Railway persistent volume via DATA_DIR (from verification module)
from verification import DATA_DIR

print("🔍 Token check results:")
print(f"- TELEGRAM_BOT_TOKEN: {'✅ Found' if TOKEN else '❌ Missing'}")
print(f"- MORALIS_API_KEY: {'✅ Found' if MORALIS_API_KEY else '❌ Missing'}")

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is required but missing!")
    print("Available env vars with 'TOKEN' or 'API':", [k for k in os.environ.keys() if 'TOKEN' in k or 'API' in k])
    print("All env vars:", list(os.environ.keys())[:10], "..." if len(os.environ) > 10 else "")
    print("Continuing with limited functionality...")

print("✅ Environment check passed:")
print(f"- TELEGRAM_BOT_TOKEN: {'✅ Set' if TOKEN else '❌ Missing'}")
print(f"- MORALIS_API_KEY: {'✅ Set' if MORALIS_API_KEY else '❌ Missing'}")
print(f"- DATA_DIR: {DATA_DIR}")
print(f"- ADMIN_USER_ID: {ADMIN_USER_ID}")

# Railway 2025 debugging - check volume mount
print(f"🔍 Volume diagnostics:")
print(f"- DATA_DIR exists: {os.path.exists(DATA_DIR)}")
print(f"- DATA_DIR writable: {os.access(DATA_DIR, os.W_OK) if os.path.exists(DATA_DIR) else 'N/A'}")
print(f"- Current working dir: {os.getcwd()}")
print(f"- /app exists: {os.path.exists('/app')}")
print(f"- /app/data exists: {os.path.exists('/app/data')}")

# Try to create DATA_DIR if it doesn't exist
if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"✅ Created DATA_DIR: {DATA_DIR}")
    except Exception as e:
        print(f"❌ Failed to create DATA_DIR: {e}")
        # Don't exit - continue with current directory
        DATA_DIR = "."
        print(f"🔄 Falling back to current directory: {DATA_DIR}")

if not MORALIS_API_KEY:
    print("WARNING: MORALIS_API_KEY not found in .env file. Using fallback RPC method.")

# Additional file paths not in verification module
VERIFICATION_LINKS_PATH = os.path.join(DATA_DIR, "verification_links.json")
VERIFICATION_INTERVAL = 23000  # Checks every 16.6 minutes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ADD THESE LINES TO REDUCE VERBOSE HTTP LOGGING
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.INFO)


# Store setup sessions and verification sessions
setup_sessions = {}
verification_sessions = {}

# Bot username (will be set after bot starts)
BOT_USERNAME = None

# ---------------------------------------------
# Utility Functions (additional to verification module)
# ---------------------------------------------
def is_admin(member):
    """Check if user is admin."""
    return member.status in ["administrator", "creator"]


def is_valid_float(value):
    """Check if value is a valid float."""
    try:
        float(value)
        return True
    except ValueError:
        return False

# Whitelist functions are now imported from verification module

# 3-Strike functions are now imported from verification module

# ---------------------------------------------
# Verification Link Management
# ---------------------------------------------
def generate_verification_link(group_id):
    """Generate a unique verification link for a group."""
    global BOT_USERNAME
    verification_links = load_json_file(VERIFICATION_LINKS_PATH)
    
    # Generate a unique token
    token = secrets.token_urlsafe(16)
    
    # Store the link mapping
    verification_links[token] = group_id
    
    # Save to file
    save_json_file(VERIFICATION_LINKS_PATH, verification_links)
    
    # Return the deep link URL with bot username
    if BOT_USERNAME:
        return f"https://t.me/{BOT_USERNAME}?start={token}"
    else:
        return f"https://t.me/wenpadgatebot?start={token}"

def get_group_from_token(token):
    """Get group ID from verification token."""
    verification_links = load_json_file(VERIFICATION_LINKS_PATH)
    return verification_links.get(token)

# Web3 verification functions are now imported from verification module


# ---------------------------------------------
# Setup Flow Functions
# ---------------------------------------------
async def handle_setup_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle responses during setup flow (Solana version)."""
    user_id = update.message.from_user.id
    message_text = update.message.text.strip()  # keep original case for addresses

    # Check if this is a group and if group is blocked (3-strike policy)
    if update.message.chat.type in ["group", "supergroup"]:
        group_id = str(update.message.chat_id)
        if is_group_blocked(group_id):
            return  # ignore blocked groups

    if user_id not in setup_sessions:
        return  # Not in setup flow
    
    session = setup_sessions[user_id]
    step = session["step"]
    group_id = session["group_id"]
    
    if step == "confirm_overwrite":
        if message_text.lower() in ["yes", "y"]:
            # skip chain selection, hardcode Solana
            session["data"]["chain_id"] = "solana"
            session["step"] = "token_address"
            await update.message.reply_text("Enter the token mint address:")
        else:
            await update.message.reply_text("❌ Setup cancelled.")
            del setup_sessions[user_id]
    
    elif step == "token_address":
        if not is_valid_ethereum_address(message_text):  # still using the validator
            await update.message.reply_text("Invalid Solana address format. Please enter a valid mint address:")
            return
        
        session["data"]["token"] = message_text
        session["step"] = "min_balance"
        await update.message.reply_text("Enter the minimum required token balance (e.g., 1.5):")
    
    elif step == "min_balance":
        if not is_valid_float(message_text) or float(message_text) <= 0:
            await update.message.reply_text("Invalid amount. Please enter a positive number (e.g., 1.5):")
            return
        
        session["data"]["min_balance"] = float(message_text)
        session["step"] = "verifier_address"
        await update.message.reply_text(
            "Enter the verifier wallet address (where users will send 1 token to verify ownership):"
        )
    
    elif step == "verifier_address":
        if not is_valid_ethereum_address(message_text):  # validator reused for Solana
            await update.message.reply_text("Invalid Solana address format. Please enter a valid wallet address:")
            return
        
        session["data"]["verifier"] = message_text
        await complete_setup(update, user_id, group_id)


async def ask_token_address(update: Update, user_id: int, group_id: int):
    """Ask user for token address (Solana hardcoded)."""
    setup_sessions[user_id] = {
        "group_id": group_id,
        "step": "token_address",
        "data": {"chain_id": "solana"}
    }
    await update.message.reply_text("Enter the token mint address:")

async def handle_setup_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle responses during setup flow."""
    user_id = update.message.from_user.id
    message_text = update.message.text.strip()  # Preserves original case
    if update.message.chat.type in ["group", "supergroup"]:
        group_id = str(update.message.chat_id)
        if is_group_blocked(group_id):
            return
    if user_id not in setup_sessions:
        return

    session = setup_sessions[user_id]
    if session and "step" in session:  # Ensure session has a step before processing
        step = session["step"]
        group_id = session["group_id"]

        if step == "token_address":
            if not is_valid_ethereum_address(message_text):  # Uses original case for Solana address
                keyboard = [
                    [
                        InlineKeyboardButton("Retry", callback_data="retry_token_address"),
                        InlineKeyboardButton("Cancel", callback_data="cancel_setup")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Invalid Solana address format. Please try again or cancel setup.",
                    reply_markup=reply_markup
                )
                return
            session["data"]["token"] = message_text  # Stores original case
            session["step"] = "min_balance"
            await update.message.reply_text("Enter the minimum required token balance (e.g., 1.5):")

        elif step == "min_balance":
            if not is_valid_float(message_text) or float(message_text) <= 0:
                keyboard = [
                    [
                        InlineKeyboardButton("Retry", callback_data="retry_min_balance"),
                        InlineKeyboardButton("Cancel", callback_data="cancel_setup")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Invalid amount. Please enter a positive number (e.g., 1.5) or cancel setup.",
                    reply_markup=reply_markup
                )
                return
            session["data"]["min_balance"] = float(message_text)
            session["step"] = "verifier_address"
            await update.message.reply_text("Enter the verifier wallet address (where users will send 1 token to verify ownership):")

        elif step == "verifier_address":
            if not is_valid_ethereum_address(message_text):  # Uses original case for Solana address
                keyboard = [
                    [
                        InlineKeyboardButton("Retry", callback_data="retry_verifier_address"),
                        InlineKeyboardButton("Cancel", callback_data="cancel_setup")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "Invalid Solana address format. Please try again or cancel setup.",
                    reply_markup=reply_markup
                )
                return
            session["data"]["verifier"] = message_text  # Stores original case
            await complete_setup(update, user_id, group_id)

async def handle_setup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle setup flow button clicks."""
    query = update.callback_query
    user_id = query.from_user.id
    callback_data = query.data

    if user_id not in setup_sessions:
        await query.answer("Session expired or invalid action.")
        return

    session = setup_sessions[user_id]
    step = session["step"]
    group_id = session["group_id"]

    if callback_data == "cancel_setup":
        await query.edit_message_text("Setup cancelled.")
        del setup_sessions[user_id]
    elif callback_data == "retry_token_address" and step == "token_address":
        await query.edit_message_text("Please enter the token mint address:")
    elif callback_data == "retry_min_balance" and step == "min_balance":
        await query.edit_message_text("Enter the minimum required token balance (e.g., 1.5):")
    elif callback_data == "retry_verifier_address" and step == "verifier_address":
        await query.edit_message_text("Enter the verifier wallet address (where users will send 1 token to verify ownership):")

    await query.answer()  # Acknowledge the callback

async def complete_setup(update: Update, user_id: int, group_id: int):
    """Complete the setup process."""
    session = setup_sessions[user_id]
    config_data = session["data"]
    
    config = load_json_file(CONFIG_PATH)
    config[group_id] = config_data
    
    if save_json_file(CONFIG_PATH, config):
        verification_link = generate_verification_link(group_id)
        
        await update.message.reply_text(
            "✅ Setup completed!\n\n"
            f"• Chain: Solana\n"
            f"• Token: {config_data['token']}\n"
            f"• Min Balance: {config_data['min_balance']}\n"
            f"• Verifier: {config_data['verifier']}\n\n"
            "Share this verification link with your members:\n"
            f"{verification_link}\n\n"
            "Users must verify BEFORE joining the group. "
            "They will receive an invite link after successful verification."
        )
    else:
        await update.message.reply_text("Failed to save configuration. Please try again.")
    
    # Clean up session
    del setup_sessions[user_id]

# ---------------------------------------------
# Whitelist Management
# ---------------------------------------------
async def handle_whitelist_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle whitelist approval/rejection buttons."""
    query = update.callback_query
    await query.answer()
    
    # Check if user is the admin
    if not is_owner(query.from_user.id):
        await query.edit_message_text("❌ Only the bot owner can approve requests.")
        return
    
    action, group_id = query.data.split('_', 1)
    
    if action == "approve":
        # Get group info BEFORE removing from pending
        pending = load_json_file(PENDING_WHITELIST_PATH)
        group_info = pending.get(group_id, {})
        group_name = group_info.get("group_name", f"Group {group_id}")
        admin_id = group_info.get("admin_id")

        if whitelist_group(group_id):
            remove_pending_whitelist(group_id)

            # Notify the group directly
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text=(
                        "✅ **GROUP APPROVED!** ✅\n\n"
                        f"Congratulations! Your group '{group_name}' has been approved.\n\n"
                        "**Next Steps:**\n"
                        "1. Use `/setup` in your group to configure token requirements\n"
                        "2. Set the bot as an admin with permission to add/remove members\n"
                        "3. Share the verification link with your members\n\n"
                        "Your group is now ready for token-gated access!"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error notifying group {group_id}: {e}")
            
            await query.edit_message_text(f"✅ Group {group_id} has been whitelisted.")
        else:
            await query.edit_message_text("❌ Failed to whitelist group.")
    
    elif action == "reject":
        # Get group info before removing from pending
        pending = load_json_file(PENDING_WHITELIST_PATH)
        group_info = pending.get(group_id, {})
        group_name = group_info.get("group_name", f"Group {group_id}")
        admin_id = group_info.get("admin_id")
        admin_name = group_info.get("admin_name")

        # Track the rejection and check if group should be blocked
        is_blocked = track_rejection(group_id, group_name, admin_id, admin_name)

        # Remove from pending
        remove_pending_whitelist(group_id)

        # Get current rejection count for display
        rejection_count = get_rejection_count(group_id)

        # Notify the group admin about rejection
        if admin_id:
            try:
                if is_blocked:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text="🚫 **GROUP PERMANENTLY BLOCKED** 🚫\n\n"
                             f"Your group '{group_name}' has been rejected for the 3rd time and is now permanently blocked.\n\n"
                             "**What this means:**\n"
                             "• Your group can no longer submit whitelist requests\n"
                             "• The bot will ignore all commands from your group\n"
                             "• The bot will ignore all activity in your group\n\n"
                             "If you believe this is an error, contact @rain5966",
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text="❌ **Whitelist Request Rejected** ❌\n\n"
                             f"Your group '{group_name}' has been rejected.\n\n"
                             f"**Strike Count:** {rejection_count}/3\n\n"
                             "⚠️ **Warning:** After 3 rejections, your group will be permanently blocked.\n\n"
                             "You can submit a new whitelist request, but please ensure you meet all requirements. "
                             "Contact @rain5966 for clarification on requirements.",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"Error notifying admin about rejection: {e}")

        if is_blocked:
            await query.edit_message_text(
                f"❌ Group {group_id} has been rejected.\n"
                f"🚫 **GROUP BLOCKED** - This group has reached 3 rejections and is now permanently blocked.\n"
                f"Total rejections: {rejection_count}/3\n"
                f"Admin has been notified."
            )
        else:
            await query.edit_message_text(
                f"❌ Group {group_id} has been rejected.\n"
                f"Rejections: {rejection_count}/3\n"
                f"Admin has been notified about the 3-strike policy."
            )

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin commands for whitelist management."""
    # Check if user is the admin
    if not is_owner(update.message.from_user.id):
        await update.message.reply_text("❌ This command is for bot owner only.")
        return
    
    if not context.args:
        # Show admin help
        await update.message.reply_text(
            "👑 *Admin Commands* 👑\n\n"
            "**Whitelist Management:**\n"
            "/admin pending - View pending whitelist requests\n"
            "/admin approve <group_id> - Approve a group\n"
            "/admin reject <group_id> - Reject a group\n"
            "/admin list - List all whitelisted groups\n\n"
            "**3-Strike System Management:**\n"
            "/admin blocked - List all blocked groups\n"
            "/admin rejections - Show all groups with rejections\n"
            "/admin strikes <group_id> - Show rejection count for a group\n"
            "/admin unblock <group_id> - Reset rejection count and unblock a group",
            parse_mode="Markdown"
        )
        return
    
    command = context.args[0].lower()
    
    if command == "pending":
        # Show pending requests
        pending = load_json_file(PENDING_WHITELIST_PATH)
        if not pending:
            await update.message.reply_text("No pending whitelist requests.")
            return
        
        message = "📋 *Pending Whitelist Requests:*\n\n"
        for group_id, info in pending.items():
            message += f"• Group: {info.get('group_name', 'Unknown')}\n"
            message += f"  ID: `{group_id}`\n"
            message += f"  Admin: {info.get('admin_name', 'Unknown')}\n"
            message += f"  Admin ID: `{info.get('admin_id', 'Unknown')}`\n\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    elif command == "approve" and len(context.args) == 2:
        group_id = context.args[1]

        # Get group info before removing from pending
        pending = load_json_file(PENDING_WHITELIST_PATH)
        group_info = pending.get(group_id, {})
        group_name = group_info.get("group_name", f"Group {group_id}")
        admin_id = group_info.get("admin_id")

        if whitelist_group(group_id):
            remove_pending_whitelist(group_id)

            # Notify the group admin about approval
            if admin_id:
                try:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text="✅ **GROUP APPROVED!** ✅\n\n"
                             f"Congratulations! Your group '{group_name}' has been approved for the whitelist.\n\n"
                             "**Next Steps:**\n"
                             "1. Use `/setup` in your group to configure token requirements\n"
                             "2. Set the bot as an admin with permission to add/remove members\n"
                             "3. Share the verification link with your members\n\n"
                             "Your group is now ready for token-gated access!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error notifying admin: {e}")

            await update.message.reply_text(f"✅ Group {group_id} has been whitelisted and admin notified.")
        else:
            await update.message.reply_text("❌ Failed to whitelist group.")
    
    elif command == "reject" and len(context.args) == 2:
        group_id = context.args[1]

        # Get group info before removing from pending
        pending = load_json_file(PENDING_WHITELIST_PATH)
        group_info = pending.get(group_id, {})
        group_name = group_info.get("group_name", f"Group {group_id}")
        admin_id = group_info.get("admin_id")
        admin_name = group_info.get("admin_name")

        # Track the rejection and check if group should be blocked
        is_blocked = track_rejection(group_id, group_name, admin_id, admin_name)

        # Remove from pending
        remove_pending_whitelist(group_id)

        # Get current rejection count for display
        rejection_count = get_rejection_count(group_id)

        # Notify the group admin about rejection
        if admin_id:
            try:
                if is_blocked:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text="🚫 **GROUP PERMANENTLY BLOCKED** 🚫\n\n"
                             f"Your group '{group_name}' has been rejected for the 3rd time and is now permanently blocked.\n\n"
                             "**What this means:**\n"
                             "• Your group can no longer submit whitelist requests\n"
                             "• The bot will ignore all commands from your group\n"
                             "• The bot will ignore all activity in your group\n\n"
                             "If you believe this is an error, contact @rain5966",
                        parse_mode="Markdown"
                    )
                else:
                    await context.bot.send_message(
                        chat_id=group_id,
                        text="❌ **Whitelist Request Rejected** ❌\n\n"
                             f"Your group '{group_name}' has been rejected.\n\n"
                             f"**Strike Count:** {rejection_count}/3\n\n"
                             "⚠️ **Warning:** After 3 rejections, your group will be permanently blocked.\n\n"
                             "You can submit a new whitelist request, but please ensure you meet all requirements. "
                             "Contact @rain5966 for clarification on requirements.",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                logger.error(f"Error notifying admin about rejection: {e}")

        if is_blocked:
            await update.message.reply_text(
                f"❌ Group {group_id} has been rejected.\n"
                f"🚫 **GROUP BLOCKED** - This group has reached 3 rejections and is now permanently blocked.\n"
                f"Total rejections: {rejection_count}/3\n"
                f"Admin has been notified."
            )
        else:
            await update.message.reply_text(
                f"❌ Group {group_id} has been rejected.\n"
                f"Rejections: {rejection_count}/3\n"
                f"Admin has been notified about the 3-strike policy."
            )
    
    elif command == "list":
        whitelist = load_json_file(WHITELIST_PATH)
        if not whitelist:
            await update.message.reply_text("No groups are whitelisted yet.")
            return

        message = "✅ *Whitelisted Groups:*\n\n"
        for group_id in whitelist.keys():
            message += f"• `{group_id}`\n"

        await update.message.reply_text(message, parse_mode="Markdown")

    elif command == "blocked":
        blocked_groups = get_blocked_groups()
        if not blocked_groups:
            await update.message.reply_text("No groups are currently blocked.")
            return

        message = "🚫 *Blocked Groups (3+ rejections):*\n\n"
        for group_id, data in blocked_groups.items():
            group_name = data.get("group_name", f"Group {group_id}")
            rejection_count = data.get("rejection_count", 0)
            last_admin = data.get("last_admin_name", "Unknown")
            message += f"• **{group_name}**\n"
            message += f"  ID: `{group_id}`\n"
            message += f"  Rejections: {rejection_count}\n"
            message += f"  Last Admin: {last_admin}\n\n"

        await update.message.reply_text(message, parse_mode="Markdown")

    elif command == "rejections":
        all_rejections = get_all_rejections()
        if not all_rejections:
            await update.message.reply_text("No groups have been rejected yet.")
            return

        message = "📊 *All Groups with Rejections:*\n\n"
        for group_id, data in all_rejections.items():
            group_name = data.get("group_name", f"Group {group_id}")
            rejection_count = data.get("rejection_count", 0)
            blocked = data.get("blocked", False)
            last_admin = data.get("last_admin_name", "Unknown")
            status = "🚫 BLOCKED" if blocked else f"⚠️ {rejection_count}/3"

            message += f"• **{group_name}** {status}\n"
            message += f"  ID: `{group_id}`\n"
            message += f"  Rejections: {rejection_count}\n"
            message += f"  Last Admin: {last_admin}\n\n"

        await update.message.reply_text(message, parse_mode="Markdown")

    elif command == "strikes" and len(context.args) == 2:
        group_id = context.args[1]
        rejection_count = get_rejection_count(group_id)
        is_blocked = is_group_blocked(group_id)

        if rejection_count == 0 and not is_blocked:
            await update.message.reply_text(f"Group `{group_id}` has no rejections.")
        else:
            all_rejections = get_all_rejections()
            group_data = all_rejections.get(group_id, {})
            group_name = group_data.get("group_name", f"Group {group_id}")
            last_admin = group_data.get("last_admin_name", "Unknown")
            status = "🚫 BLOCKED" if is_blocked else f"⚠️ {rejection_count}/3"

            await update.message.reply_text(
                f"📊 **Strike Information:**\n\n"
                f"Group: {group_name}\n"
                f"ID: `{group_id}`\n"
                f"Status: {status}\n"
                f"Rejections: {rejection_count}/3\n"
                f"Last Admin: {last_admin}",
                parse_mode="Markdown"
            )

    elif command == "unblock" and len(context.args) == 2:
        group_id = context.args[1]

        # Check if group has rejections
        rejection_count = get_rejection_count(group_id)
        if rejection_count == 0:
            await update.message.reply_text(f"Group `{group_id}` has no rejections to clear.")
            return

        # Reset rejection count
        if reset_rejection_count(group_id):
            await update.message.reply_text(
                f"✅ **Group Unblocked**\n\n"
                f"Group `{group_id}` has been unblocked.\n"
                f"Rejection count reset from {rejection_count} to 0."
            )
        else:
            await update.message.reply_text(f"❌ Failed to unblock group `{group_id}`.")

    else:
        await update.message.reply_text(
            "❌ Unknown command or missing parameters.\n"
            "Use `/admin` to see available commands."
        )

# ---------------------------------------------
# DM Verification Flow - FIXED
# ---------------------------------------------
async def handle_dm_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command in DMs with verification token."""
    if update.message.chat.type != "private":
        return
    
    user_id = update.message.from_user.id

    if context.args:
        # This is a verification link
        token = context.args[0]
        group_id = get_group_from_token(token)
        
        if not group_id:
            await update.message.reply_text("❌ Invalid verification link. Please contact the group admin for a valid link.")
            return

        # 🔑 Owner bypass with group invite
        if is_owner(user_id):
            try:
                chat = await context.bot.get_chat(group_id)
                invite_link = await chat.create_invite_link(
                    name=f"Owner access {user_id}",
                    member_limit=1,
                    creates_join_request=False,
                    expire_date=datetime.utcnow() + timedelta(minutes=10)
                )
                await update.message.reply_text(
                    f"👑 Owner detected!\n\n"
                    f"Here’s your invite link to **{chat.title}**:\n"
                    f"[Join Here]({invite_link.invite_link})",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error creating invite link for owner: {e}")
                await update.message.reply_text(
                    "👑 Owner detected! You are permanently whitelisted.\n\n"
                    "I couldn’t generate an invite link, please contact the group admin."
                )
            return

        # 🔍 New logic: Check if user already verified in this group
        user_data = load_json_file(USER_DATA_PATH)
        if (
            group_id in user_data
            and str(user_id) in user_data[group_id]
            and user_data[group_id][str(user_id)].get("verified", False)
        ):
            try:
                member = await context.bot.get_chat_member(chat_id=group_id, user_id=user_id)
                if member.status in ["member", "administrator", "creator"]:
                    # User is still inside the group
                    chat = await context.bot.get_chat(group_id)
                    await update.message.reply_text(
                        f"✅ You are already verified for *{chat.title}*.\n"
                        "You are also still in the group, so nothing to do here unless admin resets the bot.",
                        parse_mode="Markdown"
                    )
                    return
                else:
                    # User was verified before, but left the group – give new invite
                    chat = await context.bot.get_chat(group_id)
                    invite_link = await chat.create_invite_link(
                        name=f"Rejoin {user_id}",
                        member_limit=1,
                        creates_join_request=False,
                        expire_date=datetime.utcnow() + timedelta(minutes=10)
                    )
                    await update.message.reply_text(
                        f"🔄 You were previously verified for *{chat.title}*, "
                        f"but you are not in the group right now.\n\n"
                        f"Here’s a new invite link:\n[Join Here]({invite_link.invite_link})",
                        parse_mode="Markdown"
                    )
                    return
            except Exception as e:
                logger.error(f"Error checking membership for {user_id} in {group_id}: {e}")
   
        # Store verification session
        verification_sessions[(user_id, group_id)] = {
            "group_id": group_id,
            "step": "awaiting_address",
            "address": None
        }
        
        keyboard = [
            [InlineKeyboardButton("📝 Enter Wallet Address", callback_data="enter_address")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verification")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔐 *Biggie Verification* 🔐\n\n"
            "Welcome to the token verification process!\n\n"
            "To join the private group, you must verify your token holdings.\n\n"
            "Click the button below to enter your wallet address and begin verification.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        # Regular /start command in DM
        if is_owner(user_id):
            await update.message.reply_text(
                "👑 Hello Owner! You are permanently whitelisted in all groups. "
                "Click a verification link to get an invite directly."
            )
        else:
            await update.message.reply_text(
                "👋 Hello! I'm Biggie The American Bully (Top Dog Check), The Top Dog verifier! 🐕\n\n"
                "I help private groups verify token ownership for their members.\n\n"
                "To verify your tokens and join a private group, you need a verification link from the group admin.\n\n"
                "📋 *How it works:*\n"
                "1. Get a verification link from the group admin\n"
                "2. Click the link to start this verification process\n"
                "3. Provide your Ethereum wallet address\n"
                "4. I'll check if you meet the token requirements\n"
                "5. If verified, you'll receive an invite link\n\n"
                "🔒 *Your wallet address is only used for verification and is not stored long-term.*",
                parse_mode="Markdown"
            )

async def handle_group_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command in groups."""
    user_id = update.message.from_user.id

    # Check if group is blocked (3-strike policy)
    group_id = str(update.message.chat_id)
    if is_group_blocked(group_id):
        # Ignore all input from blocked groups - don't respond
        return
    
    # Special message for owner
    if is_owner(user_id):
        await update.message.reply_text(
            "👑 I'm Biggie The American Bully (Top Dog Check), The Top Dog verifier. You own me! "
            "Stop helping so much and let the project admin/owner do this."
        )
    else:
        await update.message.reply_text(
            "I'm Biggie The American Bully (Top Dog Check), The Top Dog verifier. I verify token balances and manage access to your group.\n"
            "Use /help to see available commands, or if you are ready to gate this group, use /setup."
        )

async def handle_verification_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verification button clicks."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if is_owner(user_id):
        await query.edit_message_text(
            "👑 Owner privileges: You are permanently whitelisted in all groups. "
            "No verification needed."
        )
        return

    # Find the user's session
    user_session = None
    session_key = None
    for key, session in verification_sessions.items():
        if key[0] == user_id:  # key[0] is user_id in the tuple (user_id, group_id)
            user_session = session
            session_key = key
            break

    if not user_session:
        await query.edit_message_text(
            "Your verification session has expired. Please get a new verification link from your group admin."
        )
        return

    if query.data == "enter_address":
        user_session["step"] = "awaiting_address"
        await query.edit_message_text(
            "Please send your Ethereum wallet address (starting with 0x):"
        )

    elif query.data == "cancel_verification":
        del verification_sessions[session_key]
        await query.edit_message_text(
            "Verification cancelled. You can start again anytime with a new verification link."
        )

    # ✅ NEW BRANCH: Done button
    elif query.data == "done_transfer":
        verifying_msg = await query.edit_message_text("🔍 Verifying your token transfer...")

        now = int(time.time())
        if "first_fail_time" not in user_session:
            user_session["first_fail_time"] = now

        # make sure state is correct
        user_session["step"] = "awaiting_transfer"

        if "address" not in user_session:
            await verifying_msg.edit_text(
                "⚠️ Missing wallet address in session. Please restart verification with a new link."
            )
            del verification_sessions[session_key]
            return

        config = load_json_file(CONFIG_PATH)
        group_config = config.get(user_session["group_id"])

        transfer_verified = await check_token_transfer_moralis(
            group_config['verifier'],
            user_session['address'],
            group_config['token'],
            group_config.get('chain_id', 'eth')
        )

        if transfer_verified:
            # ✅ Success
            user_data = load_json_file(USER_DATA_PATH)
            if user_session["group_id"] not in user_data:
                user_data[user_session["group_id"]] = {}

            user_data[user_session["group_id"]][str(user_id)] = {
                "address": user_session["address"],
                "verified": True,
                "last_verified": now,
                "verification_tx": True
            }
            save_json_file(USER_DATA_PATH, user_data)

            try:
                chat = await context.bot.get_chat(user_session["group_id"])
                invite_link = await chat.create_invite_link(
                    name=f"Verified member {user_id}",
                    member_limit=1,
                    creates_join_request=False,
                    expire_date=datetime.utcnow() + timedelta(minutes=10)
                )

                await verifying_msg.edit_text(
                    "✅ *Verification Complete!* ✅\n\n"
                    "You have successfully verified and proven wallet ownership! 🎉\n\n"
                    f"Here's your invite link:\n[Join Here]({invite_link.invite_link})",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error creating invite link: {e}")
                await verifying_msg.edit_text(
                    "✅ *Verification Complete!* ✅\n\n"
                    "You're verified, but I couldn't generate the invite link. Ask the group admin.",
                    parse_mode="Markdown"
                )

            del verification_sessions[session_key]

        else:
            timeout_seconds = 300
            elapsed = now - user_session["first_fail_time"]
            remaining = timeout_seconds - elapsed

            if elapsed > timeout_seconds:
                del verification_sessions[session_key]
                await verifying_msg.edit_text(
                    "❌ *Verification Timed Out* ❌\n\n"
                    "No valid transfer detected within 5 minutes.\n"
                    "Please restart verification using a new link from your group admin.",
                    parse_mode="Markdown"
                )
                return

            # ❌ Not verified yet → Retry/Cancel
            keyboard = [
                [InlineKeyboardButton("🔁 Retry Again", callback_data="retry_transfer_check")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verification")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await verifying_msg.edit_text(
                f"❌ *Transfer Not Verified Yet* ❌\n\n"
                f"It can take a few minutes for the blockchain to confirm your transfer.\n"
                f"You still have {remaining} seconds before this session expires.\n\n"
                "Wait at least a minute, then tap below to try again.",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

    elif query.data == "retry_transfer_check":
        # Enforce cooldown between retries
        now = int(time.time())
        last_retry = user_session.get("last_retry", 0)
        if now - last_retry < 60:
            wait_time = 60 - (now - last_retry)
            await query.edit_message_text(
                f"⏳ Please wait {wait_time} seconds before retrying.",
                parse_mode="Markdown"
            )
            return

        user_session["last_retry"] = now

        # Timeout tracking
        timeout_seconds = 300
        elapsed = now - user_session["first_fail_time"]

        if elapsed > timeout_seconds:
            del verification_sessions[session_key]
            await query.edit_message_text(
                "❌ *Verification Timed Out* ❌\n\n"
                "No valid transfer detected within 5 minutes.\n"
                "Please restart verification using a new link from your group admin.",
                parse_mode="Markdown"
            )
            return

        if user_session.get("step") == "awaiting_transfer" and "address" in user_session:
            verifying_msg = await query.edit_message_text("🔍 Retrying verification...")

            config = load_json_file(CONFIG_PATH)
            group_config = config.get(user_session["group_id"])

            transfer_verified = await check_token_transfer_moralis(
                group_config['verifier'],
                user_session['address'],
                group_config['token'],
                group_config.get('chain_id', 'eth')
            )

            if transfer_verified:
                # ✅ Success
                user_data = load_json_file(USER_DATA_PATH)
                if user_session["group_id"] not in user_data:
                    user_data[user_session["group_id"]] = {}

                user_data[user_session["group_id"]][str(user_id)] = {
                    "address": user_session["address"],
                    "verified": True,
                    "last_verified": now,
                    "verification_tx": True
                }

                save_json_file(USER_DATA_PATH, user_data)

                try:
                    chat = await context.bot.get_chat(user_session["group_id"])
                    invite_link = await chat.create_invite_link(
                        name=f"Verified member {user_id}",
                        member_limit=1,
                        creates_join_request=False,
                        expire_date=datetime.utcnow() + timedelta(minutes=10)
                    )

                    await verifying_msg.edit_text(
                        "✅ *Verification Complete!* ✅\n\n"
                        "You have successfully verified and proven wallet ownership! 🎉\n\n"
                        f"Here's your invite link:\n[Join Here]({invite_link.invite_link})",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error creating invite link: {e}")
                    await verifying_msg.edit_text(
                        "✅ *Verification Complete!* ✅\n\n"
                        "You're verified, but I couldn't generate the invite link. Ask the group admin.",
                        parse_mode="Markdown"
                    )

                del verification_sessions[session_key]

            else:
                remaining = timeout_seconds - elapsed
                keyboard = [
                    [InlineKeyboardButton("🔁 Retry Again", callback_data="retry_transfer_check")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verification")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await verifying_msg.edit_text(
                    f"❌ *Still Not Verified* ❌\n\n"
                    f"The transfer is still not visible.\n"
                    f"You still have {remaining} seconds before this session expires.\n\n"
                    "Make sure the transaction is confirmed and you sent exactly 1 token.\n"
                    "Retry after 1 minute if needed.",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text("⚠️ Session expired or invalid. Please restart verification.")

# ---------------------------------------------
# Enhanced Verification Flow with Token Transfer
# ---------------------------------------------
async def handle_dm_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in DMs for verification."""
    if update.message.chat.type != "private":
        return
    
    user_id = update.message.from_user.id
    message_text = update.message.text.strip()
    
    # Check if user is the owner - bypass verification
    if is_owner(user_id):
        await update.message.reply_text("👑 Owner detected!")
        return
    
    # Find the user's session
    user_session = None
    session_key = None
    for key, session in verification_sessions.items():
        if key[0] == user_id:  # key[0] is user_id in the tuple (user_id, group_id)
            user_session = session
            session_key = key
            break
    
    if not user_session:
        await update.message.reply_text(
            "Please use a verification link from your group admin to start the verification process."
        )
        return
    
    # ✅ FIXED: use session_key instead of rebuilding tuple
    session = verification_sessions[session_key]
    
    if session["step"] == "awaiting_address":
        if is_valid_ethereum_address(message_text):
            session["address"] = message_text
            session["step"] = "checking_balance"
            
            # NEW: one-wallet-per-user per group (prevent reuse by someone else)
            user_data = load_json_file(USER_DATA_PATH)
            group_users = user_data.get(session["group_id"], {})
            for uid, rec in group_users.items():
                if (
                    rec.get("address", "").lower() == message_text.lower()
                    and uid != str(user_id)
                    and rec.get("verified", False) is True
                ):
                    await update.message.reply_text(
                        "❌ This wallet is already linked to another verified member of this group. "
                        "Use a different wallet or ask the admin to reset them."
                    )
                    # ✅ FIXED: use session_key
                    del verification_sessions[session_key]
                    return            
            
            # Verify balance first
            verifying_msg = await update.message.reply_text("🔍 Checking your token balance...")
            
            config = load_json_file(CONFIG_PATH)
            group_config = config.get(session["group_id"])
            
            if not group_config:
                await verifying_msg.edit_text("Group configuration not found. Please contact the group admin.")
                # ✅ FIXED: use session_key
                del verification_sessions[session_key]
                return
            
            has_balance = await verify_user_balance(group_config, message_text)
            
            if has_balance:
                # Balance is sufficient, now ask for token transfer
                session["step"] = "awaiting_transfer"
                session["verified_balance"] = True

                # ✅ NEW: Add "Done" button
                keyboard = [
                    [InlineKeyboardButton("✅ Done", callback_data="done_transfer")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await verifying_msg.edit_text(
                    f"✅ Balance verified! You hold sufficient tokens.\n\n"
                    f"To complete verification and prove wallet ownership:\n\n"
                    f"1. Send exactly **1 token** to this address:\n"
                    f"`{group_config['verifier']}`\n\n"
                    f"2. After sending, tap the button below\n\n"
                    f"🔒 *This proves you own the wallet and completes verification.*",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
            else:
                await verifying_msg.edit_text(
                    "❌ *Verification Failed* ❌\n\n"
                    "You don't meet the token requirements.\n\n"
                    f"Required: {group_config['min_balance']} tokens\n"
                    "Please try again with a different wallet or contact the group admin if you believe this is an error."
                )
                # ✅ FIXED: use session_key
                del verification_sessions[session_key]
        else:
            await update.message.reply_text("Please send a valid Ethereum wallet address (starting with 0x followed by 40 characters):")
    
    elif session["step"] == "awaiting_transfer" and message_text.lower() == "done":
        # User claims they sent the token, now verify the transaction
        verifying_msg = await update.message.reply_text("🔍 Verifying your token transfer...")
        
        # Start session timer immediately on "done"
        now = int(time.time())
        if "first_fail_time" not in session:
            session["first_fail_time"] = now
        
        config = load_json_file(CONFIG_PATH)
        group_config = config.get(session["group_id"])

        # Check if transfer occurred
        transfer_verified = False
        if MORALIS_API_KEY:
            transfer_verified = await check_token_transfer_moralis(
                group_config['verifier'],
                session['address'],
                group_config['token'],
                group_config.get('chain_id', 'eth')
            )
        else:
            transfer_verified = await check_token_transfer(
                group_config['verifier'],
                session['address'],
                group_config['token'],
                group_config.get('chain_id', 'eth')
            )

        if transfer_verified:
            # ✅ User verified successfully
            user_data = load_json_file(USER_DATA_PATH)
            if session["group_id"] not in user_data:
                user_data[session["group_id"]] = {}

            # NEW: race-safe duplicate check just before write
            for uid, rec in user_data.get(session["group_id"], {}).items():
                if (
                    rec.get("address", "").lower() == session["address"].lower()
                    and uid != str(user_id)
                    and rec.get("verified", False) is True
                ):
                    await verifying_msg.edit_text(
                        "❌ This wallet is already linked to another verified member of this group. "
                        "Use a different wallet or ask the admin to reset them."
                    )
                    # ✅ FIXED: use session_key
                    del verification_sessions[session_key]
                    return

            user_data[session["group_id"]][str(user_id)] = {
                "address": session["address"],
                "verified": True,
                "last_verified": int(time.time()),
                "verification_tx": True
            }
            save_json_file(USER_DATA_PATH, user_data)

            # Create invite link for the group
            try:
                chat = await context.bot.get_chat(session["group_id"])
                invite_link = await chat.create_invite_link(
                    name=f"Verified member {user_id}",
                    member_limit=1,
                    creates_join_request=False,
                    expire_date=datetime.utcnow() + timedelta(minutes=10)
                )
                keyboard = [[InlineKeyboardButton("✅ Join Group", url=invite_link.invite_link)]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await verifying_msg.edit_text(
                    "✅ <b>Verification Complete!</b>\n\n"
                    "You have successfully verified your token holdings and proven wallet ownership! 🎉\n\n"
                    "Click below to join the group:",
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error creating invite link: {e}")
                await verifying_msg.edit_text(
                    "✅ *Verification Complete!* ✅\n\n"
                    "You have successfully verified! 🎉\n\n"
                    "Please contact the group admin for an invite link.",
                    parse_mode="Markdown"
                )

            # ✅ Success: remove session completely
            del verification_sessions[session_key]

        else:
            # ❌ Transfer not yet found – track first failure and give user time
            now = int(time.time())
            if "first_fail_time" not in session:
                session["first_fail_time"] = now

            timeout_seconds = 300  # 5 minutes total session time
            elapsed = now - session["first_fail_time"]

            if elapsed > timeout_seconds:
                # Hard fail – end session
                del verification_sessions[session_key]
                await verifying_msg.edit_text(
                    "❌ *Verification Timed Out* ❌\n\n"
                    "No valid transfer detected within 5 minutes.\n"
                    "Please restart verification using a new link from your group admin.",
                    parse_mode="Markdown"
                )
            else:
                remaining = timeout_seconds - elapsed
                keyboard = [
                    [InlineKeyboardButton("🔁 Retry Verification", callback_data="retry_transfer_check")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel_verification")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await verifying_msg.edit_text(
                    f"❌ *Transfer Not Verified Yet* ❌\n\n"
                    f"It can take a few minutes for the blockchain to confirm your transfer.\n"
                    f"You still have {remaining} seconds before this session expires.\n\n"
                    "Wait at least a minute, then tap below to try again.",
                    parse_mode="Markdown",
                    reply_markup=reply_markup
                )
                # 👀 IMPORTANT: session is NOT deleted here — user can retry
    
    elif session["step"] == "awaiting_transfer":
        await update.message.reply_text(
            "Please send exactly 1 token to the verifier address, then type 'done'.\n\n"
            "If you've changed your mind, type 'cancel' to stop the verification."
        )


# ---------------------------------------------
# Member Handling - REMOVED GRACE PERIOD
# ---------------------------------------------
async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining the group - REMOVED GRACE PERIOD."""
    group_id = str(update.message.chat_id)
    user_id = update.message.from_user.id

    # ✅ Check if group is blocked (3-strike policy) - ignore all input
    if is_group_blocked(group_id):
        # Ignore all input from blocked groups - no actions taken
        return
    
    # Check if user is the owner - never remove owner
    if is_owner(user_id):
        # Welcome the owner
        await update.message.reply_text(
            f"👑 Welcome, Owner!"
        )
        return
    
    config = load_json_file(CONFIG_PATH)
    group_config = config.get(group_id)
    
    if not group_config:
        return  # Group not configured
    
    for new_member in update.message.new_chat_members:
        if new_member.id == context.bot.id:
            await update.message.reply_text("Thanks for adding me! Use /setup to configure token requirements.")
            return
        
        # IMMEDIATELY remove any non-verified user who joins
        user_data = load_json_file(USER_DATA_PATH)
        user_verified = user_data.get(group_id, {}).get(str(new_member.id), {}).get("verified", False)
        
        if not user_verified:
            try:
                await context.bot.ban_chat_member(chat_id=group_id, user_id=new_member.id)
                await context.bot.unban_chat_member(chat_id=group_id, user_id=new_member.id)
                
                # Send them a message with verification instructions
                verification_link = generate_verification_link(group_id)
                
                try:
                    await context.bot.send_message(
                        chat_id=new_member.id,
                        text="❌ *Access Denied* ❌\n\n"
                             "You tried to join a private token-gated group without verification.\n\n"
                             "To join this group, you must:\n"
                             "1. Verify your token holdings first\n"
                             "2. Receive an invite link\n"
                             "3. Then join the group\n\n"
                             f"Start verification here: {verification_link}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Could not DM user: {e}")
                
            except Exception as e:
                logger.error(f"Error removing unverified user: {e}")

# ---------------------------------------------
# Debug Commands for Testing
# ---------------------------------------------
async def test_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test verification immediately (owner only)."""
    if not is_owner(update.message.from_user.id):
        await update.message.reply_text("❌ Owner only command.")
        return
    
    config = load_json_file(CONFIG_PATH)
    if not config:
        await update.message.reply_text("❌ No groups configured!")
        return
    
    await update.message.reply_text("🔄 Running test verification...")
    
    for group_id, group_config in config.items():
        await update.message.reply_text(f"🔍 Testing group {group_id}...")
        await verify_all_members(context.bot, group_id, group_config)
    
    await update.message.reply_text("✅ Test verification completed!")

# ---------------------------------------------
# Bot Commands
# ---------------------------------------------

async def set_bot_commands(application: Application):
    """Set up the bot commands menu for Telegram."""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help menu"),
        BotCommand("guide", "Complete step-by-step guide"),
        BotCommand("setup", "Setup group token requirements (admin only)"),
        BotCommand("status", "Show group settings & verification link"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot commands menu set up")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message in groups."""
    user_id = update.message.from_user.id

    # Check if this is a group and if group is blocked (3-strike policy)
    if update.message.chat.type in ["group", "supergroup"]:
        group_id = str(update.message.chat_id)
        if is_group_blocked(group_id):
            # Ignore all input from blocked groups - don't respond
            return
    
    # Special message for owner
    if is_owner(user_id):
        await update.message.reply_text(
            "👑 I'm Biggie The American Bully (Top Dog Check), The Top Dog verifier. You own me! "
        )
    else:
        await update.message.reply_text(
            "I'm Biggie The American Bully (Top Dog Check), The Top Dog verifier. I verify token balances and manage access to your group.\n"
            "Use /help to see available commands."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help menu."""
    user_id = update.message.from_user.id

    # Check if this is a group and if group is blocked (3-strike policy)
    if update.message.chat.type in ["group", "supergroup"]:
        group_id = str(update.message.chat_id)
        if is_group_blocked(group_id):
            # Ignore all input from blocked groups - don't respond
            return
    
    if is_owner(user_id):
        await update.message.reply_text("""
👑 *Owner Commands* 👑
/setup - Setup group token rules (bypasses whitelist)
/admin - Manage whitelist requests
/status - Check group settings
/guide - Complete step-by-step guide
/test_verify - Run verification immediately (testing)
/testbalance <wallet_address> <token_address> [chain_id] - Test token balance across APIs
/dump - dump the config/user data straight into your Telegram DM
/admin blocked - List all blocked groups
/admin rejections - Show all groups with rejections
/admin strikes <group_id> - Show rejection count for a specific group
/admin unblock <group_id> - Reset rejection count and unblock a group
/help - Show this help menu
""")
    else:
        await update.message.reply_text("""
*Available Commands:*

👨‍💼 *For Group Admins:*
/setup - Setup your group with token rules
/status - View current group settings & get verification link
/testbalance <wallet_address> <token_address> [chain_id] - Test token balance across APIs
/guide - Complete step-by-step setup guide

👤 *For Members:*
/guide - How to verify and join private groups
/help - Show this help menu

*Need help?* Use /guide for complete instructions or contact your group admin.
""", parse_mode="Markdown")

async def guide_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show complete step-by-step guide for admins and users."""
    user_id = update.message.from_user.id
    chat_type = update.message.chat.type

    # Check if this is a group and if group is blocked (3-strike policy)
    if chat_type in ["group", "supergroup"]:
        group_id = str(update.message.chat_id)
        if is_group_blocked(group_id):
            # Ignore all input from blocked groups - don't respond
            return
    
    if chat_type in ["group", "supergroup"]:
        # Group guide - for admins
        guide_text = """
📖 *Complete Admin Guide - Biggie The American Bully (Top Dog Check) * 📖

*1. GET WHITELISTED (First Time Only)*
• Use `/setup` in your group
• DM @rain5966 with your request
• Send a one time fee of 0.1 ETH to: `0x00000000B8f2Fa0BCfB6d540669BA4FB6CF76611`
• Wait for approval notification

*2. SETUP YOUR GROUP*
• Set bot as admin with add and remove members permissions
• Use `/setup` after approval
• Follow the interactive setup:
  - Enter chain (currently only ETH)
  - Enter token contract address
  - Enter minimum required balance
  - Enter verifier wallet address

*3. SHARE VERIFICATION LINK*
• Use `/status` to get your unique verification link
• Share this link with your members
• Members MUST verify BEFORE joining

*4. MEMBER VERIFICATION PROCESS*
1. Member clicks your verification link
2. They DM the bot with their wallet address
3. Bot checks if they hold enough tokens
4. If yes, they send 1 token to verifier address
5. Bot verifies the transfer
6. Member receives instant invite link

*5. AUTOMATIC PROTECTION*
• Bot automatically removes unverified users
• Periodic checks ensure members still hold tokens
• No grace period - verification required first

🔧 *Admin Commands:*
`/setup` - Configure group requirements
`/status` - View settings & get verification link
`/testbalance` - Usage: /testbalance <wallet_address> <token_address>
`/help` - Show all commands

Need help? Contact @rain5966
"""
    else:
        # DM guide - for users
        guide_text = """
📖 *Complete User Guide - Biggie The American Bully (Top Dog Check)* 📖

*HOW TO JOIN A PRIVATE GROUP:*

*1. GET VERIFICATION LINK*
• Ask the group admin for a verification link
• The link looks like: `t.me/biggienator_bot?start=AbCdEfGh123456`

*2. START VERIFICATION*
• Click the verification link
• You'll be redirected to this bot
• Tap "Enter Wallet Address" button

*3. PROVIDE WALLET ADDRESS*
• Send your Ethereum wallet address (starts with 0x)
• Example: `0x742d35Cc6634C0532925a3b844Bc454e4438f44e`
• Bot will check your token balance

*4. COMPLETE OWNERSHIP PROOF*
• If you have enough tokens, you'll be asked to:
• Send exactly **1 token** to the verifier address
• This proves you own the wallet
• After sending, type 'done' in this chat

*5. RECEIVE INVITE LINK*
• Bot will verify your transfer
• You'll receive a one-time invite link
• Click the link to join the private group

*IMPORTANT NOTES:*
🔒 Your wallet address is only used for verification
⏰ Invite links expire quickly (use immediately)
🔄 If transfer isn't detected, use "Retry" button
❌ Don't join the group without verification - you'll be removed

Need help? Contact your group admin first, then @rain5966
"""
    
    await update.message.reply_text(guide_text, parse_mode="Markdown")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current group settings (admin/owner only)."""
    group_id = str(update.message.chat_id)
    user_id = update.message.from_user.id

    # ✅ Step 0: Check if group is blocked (3-strike policy)
    if is_group_blocked(group_id):
        # Ignore all input from blocked groups - don't respond
        return

    # ✅ Step 1: Block non-admins and non-owner immediately
    try:
        member = await context.bot.get_chat_member(chat_id=group_id, user_id=user_id)
        if not is_admin(member) and not is_owner(user_id):
            await update.message.reply_text("❌ Only group admins can view group settings.")
            return
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        await update.message.reply_text("Error verifying admin status.")
        return

    # ✅ Step 2: Owner bypass whitelist, else check group whitelist
    if not is_owner(user_id):
        if not is_group_whitelisted(group_id):
            # Distinguish between never requested vs pending
            whitelist_data = load_json_file(WHITELIST_PATH)
            if group_id not in whitelist_data:
                await update.message.reply_text(
                    "❌ This group has never been whitelisted.\n\n"
                    "Run /setup to request whitelist approval from the owner."
                )
                return

            await update.message.reply_text(
                "⏳ Your group is pending whitelist approval.\n\n"
                "You've been added to the queue. DM @rain5966 and send 0.1 ETH to "
                "0x00000000B8f2Fa0BCfB6d540669BA4FB6CF76611.\n"
                "You'll receive a notification when your group is approved."
            )
            return

    # ✅ Step 3: Show current settings (if configured)
    config = load_json_file(CONFIG_PATH)
    group_config = config.get(group_id)

    if not group_config:
        await update.message.reply_text("No setup found. Use /setup to configure.")
        return

    verification_link = generate_verification_link(group_id)
    reply = (
        f"📊 *Group Settings:*\n"
        f"• Chain: {group_config['chain_id']}\n"
        f"• Token: `{group_config['token']}`\n"
        f"• Min Balance: {group_config['min_balance']}\n"
        f"• Verifier: `{group_config['verifier']}`\n\n"
        f"🔗 *Verification Link:*\n"
        f"`{verification_link}`\n\n"
        f"Share this link with your members. They must verify BEFORE joining."
    )

    await update.message.reply_text(reply, parse_mode="Markdown")

BALANCE_APIS = [
    {
        "name": "Moralis",
        "func": get_token_balance_moralis,
        "enabled": lambda: MORALIS_API_KEY and len(MORALIS_API_KEY) > 50,
        "args": lambda wallet, token, chain: (wallet, token, CHAIN_MAP.get(chain, chain)),
    },
]

async def test_balance_all(update, context):
    """
    Telegram command: /testbalance <wallet_address> <token_address>
    Only available to owner and group admins.
    Tests available APIs with correct decimals.
    """
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if update.effective_chat.type in ["group", "supergroup"]:
        group_id = str(chat_id)
        if is_group_blocked(group_id):
            return

    async def is_group_admin(chat_id, user_id):
        try:
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            return member.status in ["administrator", "creator"]
        except Exception:
            return False

    if not is_owner(user_id):
        if update.effective_chat.type in ["group", "supergroup"]:
            if not await is_group_admin(chat_id, user_id):
                await update.message.reply_text("Only the owner or group admins can use this command.")
                return
        else:
            await update.message.reply_text("This command is only available in groups and to the owner.")
            return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /testbalance <wallet_address> <token_address>")
        return

    wallet_address = args[0]
    token_address = args[1]
    chain_id = "solana"

    await update.message.reply_text(
        f"Testing balance for:\nWallet: `{wallet_address}`\nToken: `{token_address}`\nChain: Solana...",
        parse_mode="Markdown"
    )

    decimals = await get_token_decimals(token_address, chain_id)
    results = []
    for api in BALANCE_APIS:
        if not api["enabled"]():
            results.append(f"*{api['name']}*: _Not configured or unavailable_")
            continue
        try:
            func_args = api["args"](wallet_address, token_address, chain_id)
            balance = await api["func"](*func_args)
            results.append(f"*{api['name']}*: `{balance}`")
        except Exception as e:
            results.append(f"*{api['name']}*: Error - `{str(e)}`")

    await update.message.reply_text("\n".join(results), parse_mode="Markdown")

# ---------------------------------------------
# Error Handling
# ---------------------------------------------
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Optional: Notify admin of critical errors
    if isinstance(context.error, Exception):
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=f"⚠️ Bot Error: {context.error}\n\nUpdate: {update}"
            )
        except:
            pass  # Avoid infinite error loop

async def dump(update, context):
    if not is_owner(update.message.from_user.id):
        return
    config = load_json_file(CONFIG_PATH)
    user_data = load_json_file(USER_DATA_PATH)
    text = (
        f"CONFIG.json:\n{json.dumps(config, indent=2)[:2000]}\n\n"
        f"USER_DATA.json:\n{json.dumps(user_data, indent=2)[:2000]}"
    )
    await update.message.reply_text(f"```\n{text}\n```", parse_mode="Markdown")

# ---------------------------------------------
# Main - FIXED HANDLER REGISTRATION
# ---------------------------------------------
async def post_init(application: Application):
    """Get bot username after initialization and set up commands."""
    global BOT_USERNAME
    bot_info = await application.bot.get_me()
    BOT_USERNAME = bot_info.username
    logger.info(f"Bot username set to: {BOT_USERNAME}")
    
    # Set up bot commands menu
    await set_bot_commands(application)

def main():
    """Start the bot."""
    print("🔧 Creating Telegram application...")

    # Token validation passed, continuing with full bot startup

    try:
        # Create application
        app = Application.builder().token(TOKEN).post_init(post_init).build()
        print("✅ Application created successfully")
    except Exception as e:
        print(f"❌ Failed to create Telegram application: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Add handlers - FIXED: Separate handlers for group vs DM
    app.add_handler(CommandHandler("start", handle_group_start_command, filters=filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP))
    app.add_handler(CommandHandler("start", handle_dm_start_command, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("guide", guide_command))
    app.add_handler(CommandHandler(
        "setup",
        start_setup_flow,
        filters=filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP
    ))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("admin", handle_admin_commands))
    
    # Add debug commands (owner only, private chat only)
    app.add_handler(CommandHandler("test_verify", test_verify, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("testbalance", test_balance_all))
    app.add_handler(CommandHandler("dump", dump, filters=filters.ChatType.PRIVATE))
    
    # Handle whitelist approval buttons
    app.add_handler(CallbackQueryHandler(handle_whitelist_approval, pattern=r"^(approve|reject)_"))
    
    # Handle verification buttons
    app.add_handler(CallbackQueryHandler(handle_verification_button))
    
    # Handle DM messages for verification
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND, handle_dm_message))
    
    # Handle new members and setup responses
    app.add_handler(CallbackQueryHandler(handle_setup_callback, pattern=r"^(retry_token_address|retry_min_balance|retry_verifier_address|cancel_setup)$"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member)) 
    app.add_handler(
        MessageHandler(
            filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP) & ~filters.COMMAND,
            handle_setup_response
        )
    )
    
    # ADD ERROR HANDLER HERE
    app.add_error_handler(error_handler)
    
    # NOTE: Periodic verification moved to Railway cron job
    # Railway cron jobs handle scheduled tasks better than long-running job queues
    # Configure cron schedule in Railway dashboard: "0 */6 * * *" (every 6 hours)
    logger.info("✅ Bot started - periodic verification handled by Railway cron job")
    
    logger.info("Biggie on ETH is starting...")
    print(f"Bot starting with token: {TOKEN[:10]}...")
    
    # RUN WITH ERROR HANDLING
    try:
        app.run_polling(
            poll_interval=1.0,
            timeout=10,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")

# ==== CRITICAL: ADD THIS AT THE VERY END OF YOUR FILE ====
if __name__ == "__main__":
    try:
        print("🚀 Starting main() function...")
        main()
    except KeyboardInterrupt:
        print("👋 Bot stopped by user")
    except Exception as e:
        print(f"💥 FATAL ERROR in main(): {e}")
        import traceback
        traceback.print_exc()
        print("🔍 Error details:")
        print(f"- Error type: {type(e).__name__}")
        print(f"- Error message: {str(e)}")
        print("📞 Please contact support with this error log")
        exit(1)