#!/usr/bin/env python3
"""
Blockchain Integration Module for Biggie Telegram Bot
Handles all blockchain/Solana related functionality including:
- Token balance verification
- Token transfer checking
- Moralis API integration
- Solana address validation
"""

import asyncio
import logging
import re
import os
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Chain mapping for Moralis compatibility
CHAIN_MAP = {
    "solana": "mainnet",  # Use 'devnet' for testing
}

# Public RPC endpoints
PUBLIC_RPC_ENDPOINTS = {
    "solana": "https://api.mainnet-beta.solana.com",
}

# API Keys
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")

# ---------------------------------------------
# Address Validation
# ---------------------------------------------
def is_valid_ethereum_address(address):
    """Validate Solana address format (reusing name for compatibility)."""
    pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')  # Base58 regex for Solana
    return bool(pattern.match(address))

# ---------------------------------------------
# Token Metadata Functions
# ---------------------------------------------
async def get_token_decimals(token_address: str, chain_id: str = "solana") -> int:
    """
    Fetch decimals via Moralis Solana API, fallback to 9 if not available.
    """
    try:
        from moralis import sol_api
        moralis_chain = CHAIN_MAP.get(chain_id, chain_id)
        params = {
            "network": moralis_chain,
            "address": token_address
        }
        token_metadata = await asyncio.to_thread(
            sol_api.token.get_token_metadata_by_address,
            api_key=MORALIS_API_KEY,
            params=params
        )
        decimals = int(token_metadata.get("decimals", 9))
        return decimals
    except Exception as e:
        logger.error(f"Error fetching token decimals: {e}")
        return 9

# ---------------------------------------------
# Balance Checking Functions
# ---------------------------------------------
async def get_token_balance_moralis(wallet: str, token: str, chain: str = "solana") -> float:
    """Get token balance using Moralis Solana API"""
    try:
        from moralis import sol_api
        params = {
            "address": wallet,
            "network": chain
        }

        result = await asyncio.to_thread(
            sol_api.account.get_spl,
            api_key=MORALIS_API_KEY,
            params=params
        )

        if result and isinstance(result, list):
            for token_data in result:
                if token_data.get('mint', '').lower() == token.lower():
                    raw_balance = int(token_data.get('amount', 0))
                    decimals = int(token_data.get('decimals', 9))
                    return raw_balance / (10 ** decimals)

        return 0.0

    except Exception as e:
        logger.error(f"Moralis Solana API error: {e}")
        return 0.0

async def get_token_balance_etherscan(wallet: str, token: str) -> float:
    """Placeholder for compatibility (not used for Solana)."""
    logger.warning("Etherscan not supported for Solana, returning 0.0")
    return 0.0

# ---------------------------------------------
# Main Verification Function
# ---------------------------------------------
async def verify_user_balance(group_config, user_address):
    """Verify if user meets token balance requirements"""
    try:
        token_address = group_config["token"]
        min_balance = group_config["min_balance"]
        chain_id = group_config.get("chain_id", "solana")

        logger.info(f"🔍 Checking balance for {user_address} on {chain_id}")
        logger.info(f"Token: {token_address}, Min required: {min_balance}")

        balance = 0.0

        if MORALIS_API_KEY and len(MORALIS_API_KEY) > 50:
            try:
                moralis_chain = CHAIN_MAP.get(chain_id, chain_id)
                logger.info(f"Using Moralis Solana API for balance check on {moralis_chain}")
                balance = await get_token_balance_moralis(user_address, token_address, moralis_chain)
                logger.info(f"Moralis balance result: {balance}")
                if balance > 0:
                    logger.info("✅ Moralis balance check successful")
            except Exception as e:
                logger.warning(f"⚠️ Moralis failed: {e}")

        logger.info(f"📊 Final balance: {balance}, Required: {min_balance}, Sufficient: {balance >= min_balance}")

        return balance >= min_balance
    except Exception as e:
        logger.error(f"❌ Error in verify_user_balance: {e}")
        return False

# ---------------------------------------------
# Token Transfer Checking
# ---------------------------------------------
async def check_token_transfer_moralis(verifier_address, user_address, token_address, chain="solana"):
    """Check token transfers using Moralis Solana API"""
    try:
        from moralis import sol_api
        moralis_chain = CHAIN_MAP.get(chain, chain)

        # Fetch token decimals
        decimals = await get_token_decimals(token_address, chain)
        logger.info(f"Token {token_address} has decimals: {decimals}")

        # Get transfers from user to verifier
        params = {
            "address": user_address,
            "network": moralis_chain,
            "limit": 10
        }

        logger.info(f"Checking transfers for {user_address} to {verifier_address}")

        result = await asyncio.to_thread(
            sol_api.account.get_spl_transfers,
            api_key=MORALIS_API_KEY,
            params=params
        )

        transfers = result.get("result", [])
        if not isinstance(transfers, list):
            logger.error(f"Malformed transfer result: {result}")
            return False

        for transfer in transfers:
            value_raw = transfer.get('amount')
            to_addr = transfer.get('to', '').lower()
            from_addr = transfer.get('from', '').lower()
            token_addr = transfer.get('mint', '').lower()
            actual_amount = int(value_raw) / (10 ** decimals)

            logger.info(f"🔍 Transfer found:")
            logger.info(f"  From: {from_addr}")
            logger.info(f"  To: {to_addr}")
            logger.info(f"  Mint: {token_addr}")
            logger.info(f"  Value (raw): {value_raw}")
            logger.info(f"  Value (normalized): {actual_amount}")

            if (
                to_addr == verifier_address.lower()
                and token_addr == token_address.lower()
                and abs(actual_amount - 1.0) <= (1 / (10 ** decimals))
            ):
                logger.info("✅ Match found: transfer to verifier with correct amount and token")
                return True

        return False

    except Exception as e:
        logger.error(f"Moralis Solana transfers error: {e}")
        return False