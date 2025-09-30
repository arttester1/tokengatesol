#!/usr/bin/env python3
"""
Blockchain Integration Module for Biggie Telegram Bot
Handles all blockchain/ETH related functionality including:
- Token balance verification
- Token transfer checking
- Moralis and Etherscan API integration
- Ethereum address validation
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
    "eth": "eth",
    "mainnet": "eth",
    "0x1": "eth",
    "bsc": "bsc",
    "binance": "bsc",
    "0x38": "bsc",
    "polygon": "polygon",
    "matic": "polygon",
    "0x89": "polygon",
    # Add other chains as needed
}

# Public RPC endpoints
PUBLIC_RPC_ENDPOINTS = {
    "eth": "https://cloudflare-eth.com",
    "mainnet": "https://cloudflare-eth.com",
}

# API Keys
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

# ---------------------------------------------
# Address Validation
# ---------------------------------------------
def is_valid_ethereum_address(address):
    """Validate Ethereum address format."""
    pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
    return bool(pattern.match(address))

# ---------------------------------------------
# Token Metadata Functions
# ---------------------------------------------
async def get_token_decimals(token_address: str, chain_id: str = "eth") -> int:
    """
    Try to fetch decimals via Moralis, fallback to 18 if not available.
    """
    try:
        from moralis import evm_api
        moralis_chain = CHAIN_MAP.get(chain_id, chain_id)
        params = {
            "chain": moralis_chain,
            "addresses": [token_address]
        }
        token_metadata = await asyncio.to_thread(
            evm_api.token.get_token_metadata,
            api_key=MORALIS_API_KEY,
            params=params
        )
        decimals = int(token_metadata[0].get("decimals", 18))
        return decimals
    except Exception as e:
        logger.error(f"Error fetching token decimals: {e}")
        return 18

# ---------------------------------------------
# Balance Checking Functions
# ---------------------------------------------
async def get_token_balance_moralis(wallet: str, token: str, chain: str = "eth") -> float:
    """Get token balance using Moralis SDK"""
    try:
        from moralis import evm_api
        params = {
            "address": wallet,
            "chain": chain,
            "token_addresses": [token]
        }

        result = await asyncio.to_thread(
            evm_api.token.get_wallet_token_balances,
            api_key=MORALIS_API_KEY,
            params=params
        )

        if result and isinstance(result, list):
            for token_data in result:
                if token_data.get('token_address', '').lower() == token.lower():
                    raw_balance = int(token_data.get('balance', 0))
                    decimals = int(token_data.get('decimals', 18))
                    return raw_balance / (10 ** decimals)

        return 0.0

    except Exception as e:
        logger.error(f"Moralis SDK error: {e}")
        return 0.0

async def get_token_balance_etherscan(wallet: str, token: str) -> float:
    """Get token balance using Etherscan V2 REST API (with chainid=1)."""
    if not ETHERSCAN_API_KEY:
        logger.warning("No ETHERSCAN_API_KEY found, skipping fallback API.")
        return 0.0

    import aiohttp
    url = (
        f"https://api.etherscan.io/v2/api"
        f"?chainid=1"
        f"&module=account"
        f"&action=tokenbalance"
        f"&contractaddress={token}"
        f"&address={wallet}"
        f"&tag=latest"
        f"&apikey={ETHERSCAN_API_KEY}"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                result = await resp.json()
                raw_balance = int(result.get("result", "0"))
                return raw_balance  # Divide by decimals elsewhere!
    except Exception as e:
        logger.error(f"Etherscan V2 REST error: {e}")
    return 0.0

# ---------------------------------------------
# Main Verification Function
# ---------------------------------------------
async def verify_user_balance(group_config, user_address):
    """Verify if user meets token balance requirements with proper fallback"""
    try:
        token_address = group_config["token"]
        min_balance = group_config["min_balance"]
        chain_id = group_config.get("chain_id", "eth")

        logger.info(f"🔍 Checking balance for {user_address} on {chain_id}")
        logger.info(f"Token: {token_address}, Min required: {min_balance}")

        balance = 0.0

        # Only try Moralis if we have a valid-looking API key
        if MORALIS_API_KEY and len(MORALIS_API_KEY) > 50:  # Basic validation
            try:
                moralis_chain = CHAIN_MAP.get(chain_id, chain_id)
                logger.info(f"Using Moralis API for balance check on {moralis_chain}")
                balance = await get_token_balance_moralis(user_address, token_address, moralis_chain)
                logger.info(f"Moralis balance result: {balance}")
                if balance > 0:
                    logger.info("✅ Moralis balance check successful")
            except Exception as e:
                logger.warning(f"⚠️ Moralis failed, falling back to RPC: {e}")

        # If Moralis failed or returned 0, try Etherscan fallback
        if balance <= 0:
            logger.info("🔄 Using Etherscan fallback verification")
            etherscan_balance_raw = await get_token_balance_etherscan(user_address, token_address)
            # Get correct decimals
            decimals = await get_token_decimals(token_address, chain_id)
            balance = etherscan_balance_raw / (10 ** decimals)
            logger.info(f"Etherscan balance result: {balance}")

        logger.info(f"📊 Final balance: {balance}, Required: {min_balance}, Sufficient: {balance >= min_balance}")

        return balance >= min_balance
    except Exception as e:
        logger.error(f"❌ Error in verify_user_balance: {e}")
        return False

# ---------------------------------------------
# Token Transfer Checking
# ---------------------------------------------
async def check_token_transfer_moralis(verifier_address, user_address, token_address, chain="eth"):
    """Check token transfers using Moralis SDK"""
    try:
        from moralis import evm_api
        moralis_chain = CHAIN_MAP.get(chain, chain)

        # Get current block using timestamp
        params_current_block = {
            "chain": moralis_chain,
            "date": datetime.now(timezone.utc).isoformat(timespec='seconds')
        }

        current_block_data = await asyncio.to_thread(
            evm_api.block.get_date_to_block,
            api_key=MORALIS_API_KEY,
            params=params_current_block
        )
        current_block = current_block_data.get('block', 0)

        # Fetch token decimals first
        decimals_params = {
            "chain": moralis_chain,
            "addresses": [token_address]
        }

        token_metadata = await asyncio.to_thread(
            evm_api.token.get_token_metadata,
            api_key=MORALIS_API_KEY,
            params=decimals_params
        )

        decimals = int(token_metadata[0].get("decimals", 18))
        logger.info(f"Token {token_address} has decimals: {decimals}")

        # Get transfers from user to verifier within last 800 blocks
        params = {
            "address": user_address,
            "chain": moralis_chain,
            "from_block": max(0, current_block - 800),
            "to_block": current_block,
            "contract_addresses": [token_address],
            "to_address": verifier_address,
            "limit": 10
        }

        logger.info(f"Checking transfers in blocks {params['from_block']} to {params['to_block']}")

        result = await asyncio.to_thread(
            evm_api.token.get_wallet_token_transfers,
            api_key=MORALIS_API_KEY,
            params=params
        )

        transfers = result.get("result", [])
        if not isinstance(transfers, list):
            logger.error(f"Malformed transfer result: {result}")
            return False

        for transfer in transfers:
            value_raw = transfer.get('value')
            to_addr = transfer.get('to_address', '').lower()
            from_addr = transfer.get('from_address', '').lower()
            token_addr = transfer.get('address', '').lower()
            actual_amount = int(value_raw) / (10 ** decimals)

            logger.info(f"🔍 Transfer found:")
            logger.info(f"  From: {from_addr}")
            logger.info(f"  To: {to_addr}")
            logger.info(f"  Contract: {token_addr}")
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
        logger.error(f"Moralis transfers error: {e}")
        return False