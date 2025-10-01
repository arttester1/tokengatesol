#!/usr/bin/env python3
"""
Blockchain Integration Module for Biggie Telegram Bot (Solana Version)
Handles all Solana SPL token verification:
- Token balance verification
- Moralis + Solana RPC integration
"""

import asyncio
import logging
import os
import requests
import base58

logger = logging.getLogger(__name__)

# API Keys and RPC endpoint
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY")
RPC_ENDPOINT = os.getenv("SOLANA_RPC_ENDPOINT", "https://api.mainnet-beta.solana.com")

def is_valid_solana_address(address: str) -> bool:
    """Validate Solana address/mint format (base58, 32–44 chars)."""
    try:
        decoded = base58.b58decode(address)
        return len(decoded) == 32
    except Exception:
        return False


# ---------------------------------------------
# Balance Checking Functions
# ---------------------------------------------
async def get_token_balance_moralis(wallet_address: str, token_mint: str) -> float:
    """Get SPL token balance using Moralis API"""
    try:
        url = f"https://solana-gateway.moralis.io/account/mainnet/{wallet_address}/tokens?excludeSpam=true"
        headers = {"accept": "application/json", "X-API-Key": MORALIS_API_KEY}
        response = await asyncio.to_thread(requests.get, url, headers=headers)  # ✅ correct
        response.raise_for_status()

        data = response.json()
        token = next((t for t in data if t.get("mint") == token_mint), None)
        if token:
            return float(token.get("amount", "0"))
        return 0.0
    except Exception as e:
        logger.error(f"Moralis Error: {e}")
        return 0.0

async def get_token_balance_rpc(wallet_address: str, token_mint: str) -> float:
    """Get SPL token balance using Solana RPC"""
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet_address,
                {"mint": token_mint},
                {"encoding": "jsonParsed"},
            ],
        }
        headers = {"Content-Type": "application/json"}
        response = await asyncio.to_thread(requests.post, RPC_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()

        accounts = response.json()["result"]["value"]
        if accounts:
            return float(
                accounts[0]["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"]
            )
        return 0.0
    except Exception as e:
        logger.error(f"RPC Error: {e}")
        return 0.0

# ---------------------------------------------
# Main Verification Function
# ---------------------------------------------
async def verify_user_balance(group_config, user_address: str) -> bool:
    """
    Verify if user meets token balance requirements on Solana.
    Tries Moralis first, falls back to RPC.
    """
    try:
        token_mint = group_config["token"]
        min_balance = group_config["min_balance"]

        logger.info(f"🔍 Checking balance for {user_address}")
        logger.info(f"Token mint: {token_mint}, Min required: {min_balance}")

        balance = 0.0

        # Try Moralis first
        if MORALIS_API_KEY and len(MORALIS_API_KEY) > 20:
            balance = await get_token_balance_moralis(user_address, token_mint)
            logger.info(f"Moralis balance: {balance}")
            if balance > 0:
                logger.info("✅ Moralis balance check successful")

        # Fallback to RPC if Moralis fails or returns 0
        if balance <= 0:
            balance = await get_token_balance_rpc(user_address, token_mint)
            logger.info(f"RPC balance: {balance}")

        logger.info(
            f"📊 Final balance: {balance}, Required: {min_balance}, Sufficient: {balance >= min_balance}"
        )
        return balance >= min_balance

    except Exception as e:
        logger.error(f"❌ Error in verify_user_balance: {e}")
        return False


# ---------------------------------------------
# Utility (no-op for Solana version)
# ---------------------------------------------
async def get_token_decimals(token_address: str, chain_id: str = "sol") -> int:
    """
    Return token decimals. On Solana, balances are normalized already,
    so we return 0 to avoid extra scaling.
    """
    return 0


# ---------------------------------------------
# Token Transfer Checking
# ---------------------------------------------
async def check_token_transfer_moralis(verifier_address: str, user_address: str, token_mint: str, limit: int = 20) -> bool:
    """
    Check if the user sent exactly 1 SPL token (token_mint) to verifier_address.
    Uses Helius parsed transaction API instead of raw RPC.
    """
    try:
        url = f"{RPC_ENDPOINT}"
        headers = {"Content-Type": "application/json"}

        # Step 1: Get recent transactions for the user
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                user_address,
                {"limit": limit}
            ],
        }
        resp = await asyncio.to_thread(requests.post, url, json=payload, headers=headers)
        resp.raise_for_status()
        signatures = [sig["signature"] for sig in resp.json().get("result", [])]

        if not signatures:
            logger.info("No recent signatures found for user.")
            return False

        # Step 2: Ask Helius for parsed transactions (cleaner than raw RPC)
        tx_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransactions",
            "params": [signatures, {"encoding": "jsonParsed"}],
        }
        tx_resp = await asyncio.to_thread(requests.post, url, json=tx_payload, headers=headers)
        tx_resp.raise_for_status()
        txs = tx_resp.json().get("result", [])

        # Step 3: Check each transaction for a matching transfer
        for tx in txs:
            if not tx:
                continue
            instructions = tx.get("transaction", {}).get("message", {}).get("instructions", [])
            for ix in instructions:
                parsed = ix.get("parsed", {})
                if parsed.get("type") == "transfer":
                    info = parsed.get("info", {})
                    if (
                        info.get("source") == user_address
                        and info.get("destination") == verifier_address
                        and info.get("mint") == token_mint
                    ):
                        amount = float(info.get("tokenAmount", {}).get("uiAmount", 0))
                        if abs(amount - 1.0) < 1e-6:
                            logger.info(f"✅ Verified 1 token transfer from {user_address} to {verifier_address}")
                            return True

        logger.info("❌ No matching 1-token transfer found.")
        return False

    except Exception as e:
        logger.error(f"Helius transfer check error: {e}")
        return False

