"""
Solana on-chain transfer fetching via Alchemy Solana RPC.

Set ALCHEMY_SOLANA_HTTP_URL in this file or in the environment (same format as
Ethereum: use your Solana app URL from the Alchemy dashboard).
Example: https://solana-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_API_KEY
"""
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# Paste your Alchemy Solana RPC URL here (or set env ALCHEMY_SOLANA_HTTP_URL).
# Create a *Solana* app at https://dashboard.alchemy.com (separate from Ethereum).
_SOLANA_URL_DEFAULT = "https://solana-mainnet.g.alchemy.com/v2/HLK1VFEFAbDFATB6Jze1w"  # e.g. "https://solana-mainnet.g.alchemy.com/v2/your-solana-key"
ALCHEMY_SOLANA_HTTP_URL: str = os.environ.get("ALCHEMY_SOLANA_HTTP_URL", _SOLANA_URL_DEFAULT).strip()


def _resolve_solana_url() -> str:
    """Use explicit Solana URL, or try to derive from Ethereum Alchemy URL (same key)."""
    if ALCHEMY_SOLANA_HTTP_URL:
        return ALCHEMY_SOLANA_HTTP_URL.rstrip("/")
    try:
        from . import alchemy_client
        eth_url = getattr(alchemy_client, "ALCHEMY_HTTP_URL", "") or ""
        if "alchemy.com" in eth_url and "/v2/" in eth_url:
            # e.g. https://eth-mainnet.g.alchemy.com/v2/KEY -> https://solana-mainnet.g.alchemy.com/v2/KEY
            base = "https://solana-mainnet.g.alchemy.com/v2"
            key = eth_url.split("/v2/")[-1].split("?")[0].strip()
            if key:
                return f"{base}/{key}"
    except Exception:
        pass
    return ""

# USDC / USDT mints on Solana mainnet
SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"

TOKEN_MINTS: Dict[str, str] = {
    "USDC": SOLANA_USDC_MINT,
    "USDT": SOLANA_USDT_MINT,
    "SOL": "So11111111111111111111111111111111111111112",
}


def _get_solana_url() -> str:
    url = _resolve_solana_url()
    if url:
        return url
    raise RuntimeError(
        "Set ALCHEMY_SOLANA_HTTP_URL in solana_client.py or env, or create a Solana app "
        "at https://dashboard.alchemy.com and paste its URL (e.g. https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY)."
    )


def _rpc(method: str, params: Optional[List[Any]] = None) -> Any:
    url = _get_solana_url()
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    return data.get("result")


def _time_range_for_timeframe(timeframe: str) -> tuple[int, int]:
    """Return (since_unix_ts, now_unix_ts) for the given timeframe."""
    timeframe = (timeframe or "").strip().lower()
    parts = timeframe.split()
    if len(parts) < 2:
        num, unit = 1, "days"
    else:
        try:
            num = int(parts[0])
        except ValueError:
            num = 1
        unit = parts[1]
    now = int(time.time())
    if "hour" in unit:
        delta = num * 3600
    else:
        delta = num * 86400
    return now - delta, now


def _parse_token_balances_for_mint(
    meta: Dict[str, Any], mint: str
) -> List[tuple[str, float]]:
    """From parsed tx meta, return list of (owner, delta) for the given mint. Delta in human amount."""
    pre_list = meta.get("preTokenBalances") or meta.get("pre_token_balances") or []
    post_list = meta.get("postTokenBalances") or meta.get("post_token_balances") or []
    pre = {b.get("accountIndex", b.get("account_index")): b for b in pre_list if b.get("mint") == mint}
    post = {b.get("accountIndex", b.get("account_index")): b for b in post_list if b.get("mint") == mint}
    account_indices = set(pre.keys()) | set(post.keys())
    decimals = 6 if mint == SOLANA_USDC_MINT or mint == SOLANA_USDT_MINT else 9
    result: List[tuple[str, float]] = []
    for idx in account_indices:
        p = pre.get(idx)
        q = post.get(idx)
        owner = (q or p or {}).get("owner", "")
        if not owner:
            continue
        try:
            pre_ui = 0.0
            u = (p or {}).get("uiTokenAmount") or (p or {}).get("ui_token_amount")
            if p and u:
                if u.get("uiAmount", u.get("ui_amount")) is not None:
                    pre_ui = float(u.get("uiAmount", u.get("ui_amount")))
                elif u.get("amount"):
                    pre_ui = int(u["amount"]) / (10 ** int(u.get("decimals", decimals)))
            post_ui = 0.0
            u = (q or {}).get("uiTokenAmount") or (q or {}).get("ui_token_amount")
            if q and u:
                if u.get("uiAmount", u.get("ui_amount")) is not None:
                    post_ui = float(u.get("uiAmount", u.get("ui_amount")))
                elif u.get("amount"):
                    post_ui = int(u["amount"]) / (10 ** int(u.get("decimals", decimals)))
        except (TypeError, ValueError, KeyError):
            continue
        delta = post_ui - pre_ui
        if delta != 0:
            result.append((owner, delta))
    return result


def fetch_transfers_solana(
    token: Optional[str],
    timeframe: Optional[str],
    limit: Optional[int],
) -> Dict[str, Any]:
    """
    Fetch SPL token transfer data using Alchemy Solana RPC.

    Uses getTokenLargestAccounts(mint), getSignaturesForAddress, and getParsedTransaction
    to build transfer rows. Returns the same shape as Ethereum: block_time,
    block_number (slot), tx_hash (signature), from_address, to_address, amount, token_symbol.
    """
    limit = limit or 10
    try:
        _get_solana_url()
    except RuntimeError as e:
        return {"ok": False, "error": str(e), "transfers": []}

    mint = TOKEN_MINTS.get((token or "USDC").upper(), SOLANA_USDC_MINT)
    token_display = (token or "USDC").upper()
    decimals_round = 6 if token_display in ("USDC", "USDT") else 4

    # Get recent transaction signatures that involve this token mint.
    # Using getSignaturesForAddress(mint) works on Alchemy; getTokenLargestAccounts often returns 503.
    try:
        sigs = _rpc("getSignaturesForAddress", [mint, {"limit": 100}])
    except Exception as e:
        err = str(e).strip()
        if "401" in err or "403" in err or "Unauthorized" in err.lower():
            err = "Solana RPC auth failed. Create a *Solana* app at dashboard.alchemy.com and set ALCHEMY_SOLANA_HTTP_URL."
        elif "503" in err or "502" in err or "Service Unavailable" in err:
            err = "Solana RPC temporarily unavailable (503/502). Try again in a moment."
        return {"ok": False, "error": err, "transfers": []}

    if not isinstance(sigs, list) or not sigs:
        return {"ok": True, "transfers": [], "chain": "solana"}

    all_sigs = [
        {"signature": s.get("signature"), "blockTime": s.get("blockTime"), "slot": s.get("slot")}
        for s in sigs
        if s.get("signature")
    ]

    # Alchemy Solana does NOT support getParsedTransaction; getTransaction often returns null.
    # So we cannot get from/to/amount from the RPC. Return recent signatures as minimal rows
    # so the UI shows something, with a note that full details need a different provider (e.g. Helius).
    rows: List[Dict[str, Any]] = []
    for s in all_sigs[:limit]:
        sig = s.get("signature")
        if not sig:
            continue
        slot = s.get("slot") or 0
        block_time = None
        if s.get("blockTime"):
            try:
                block_time = datetime.utcfromtimestamp(s["blockTime"]).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                block_time = str(s["blockTime"])
        rows.append({
            "block_time": block_time,
            "block_number": slot,
            "tx_hash": sig,
            "from_address": "—",
            "to_address": "—",
            "amount": 0,
            "token_symbol": token_display,
        })

    # Alchemy Solana: no getParsedTransaction, getTransaction returns null — so we only have sigs.
    return {
        "ok": True,
        "transfers": rows,
        "chain": "solana",
        "notice": "Alchemy Solana does not support getParsedTransaction; amounts and addresses are not available. For full transfer details use a provider like Helius.",
    }
