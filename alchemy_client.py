import requests
from typing import Any, Dict, List, Optional

from web3 import Web3

# Paste your full Alchemy HTTP URL here and restart the server.
# Example:
# ALCHEMY_HTTP_URL = "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"
ALCHEMY_HTTP_URL: str = "https://eth-mainnet.g.alchemy.com/v2/OttGHkbjIftxoEkHEFqtr"

# Approximate blocks per day on Ethereum (~12s block time)
ETH_BLOCKS_PER_DAY = 7200

# Common ERC-20 contract addresses on Ethereum mainnet (symbol -> address)
TOKEN_CONTRACTS_ETH: Dict[str, str] = {
    "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
    "DAI": "0x6B175474E89094C44Da98b954Eedeac495271d0F",
    "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
}


def get_alchemy_url() -> str:
    """
    Return the configured Alchemy HTTP URL.
    """
    if not ALCHEMY_HTTP_URL:
        raise RuntimeError(
            "Set ALCHEMY_HTTP_URL in `alchemy_client.py` to your full Alchemy URL."
        )
    return ALCHEMY_HTTP_URL


def get_web3() -> Web3:
    """Create a Web3 client connected to Alchemy."""
    url = get_alchemy_url()
    w3 = Web3(Web3.HTTPProvider(url))
    if not w3.is_connected():
        raise RuntimeError("Could not connect to Alchemy with the provided URL.")
    return w3


def get_latest_block_summary() -> Dict[str, Any]:
    """
    Convenience helper: return a small summary of the latest Ethereum block.
    """
    w3 = get_web3()
    latest = w3.eth.get_block("latest", full_transactions=False)
    return {
        "number": latest.number,
        "hash": latest.hash.hex(),
        "timestamp": latest.timestamp,
        "transaction_count": len(latest.transactions),
    }


def _block_range_for_timeframe(timeframe: str, current_block: int) -> tuple[int, int]:
    """Convert timeframe string (e.g. '24 hours', '7 days') to (from_block, to_block)."""
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
    if "hour" in unit:
        blocks_back = num * (ETH_BLOCKS_PER_DAY // 24)
    else:
        blocks_back = num * ETH_BLOCKS_PER_DAY
    from_block = max(0, current_block - blocks_back)
    return from_block, current_block


def _alchemy_get_asset_transfers(
    from_block: int,
    to_block: int,
    category: List[str],
    max_count: int = 1000,
    contract_addresses: Optional[List[str]] = None,
    order: str = "desc",
    page_key: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Call Alchemy Transfers API; returns (transfers, next_page_key)."""
    url = get_alchemy_url()
    params: Dict[str, Any] = {
        "fromBlock": hex(from_block),
        "toBlock": "latest",  # include up to latest block (more reliable than hex(to_block))
        "category": category,
        "excludeZeroValue": True,
        "withMetadata": True,
        "maxCount": hex(min(max_count, 1000)),
        "order": order,
    }
    if contract_addresses:
        # Alchemy expects contract addresses as-is (checksum or lowercase both work)
        params["contractAddresses"] = list(contract_addresses)
    if page_key:
        params["pageKey"] = page_key
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "alchemy_getAssetTransfers",
        "params": [params],
    }
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data["error"].get("message", str(data["error"])))
    result = data.get("result") or {}
    transfers = result.get("transfers") or []
    next_key = result.get("pageKey") or None
    if next_key and isinstance(next_key, str) and next_key.strip() == "":
        next_key = None
    return transfers, next_key


# Known decimals for tokens (Alchemy sometimes omits rawContract.decimal)
TOKEN_DECIMALS: Dict[str, int] = {
    "USDC": 6,
    "USDT": 6,
    "DAI": 18,
    "WETH": 18,
}


def _transfer_value(t: Dict[str, Any], token_symbol: Optional[str] = None) -> float:
    """Extract human-readable amount. For USDC/USDT always use 6 decimals (raw/1e6)."""
    token_upper = (token_symbol or t.get("asset") or "").upper()
    is_stablecoin_6 = token_upper in ("USDC", "USDT")

    raw = t.get("rawContract") or {}
    raw_val = raw.get("value")
    if raw_val is not None:
        if isinstance(raw_val, str) and raw_val.startswith("0x"):
            raw_int = int(raw_val, 16)
        else:
            try:
                raw_int = int(raw_val)
            except (TypeError, ValueError):
                raw_int = 0
        # USDC/USDT always have 6 decimals on-chain - never trust API decimal for these
        if is_stablecoin_6:
            decimals = 6
        else:
            decimals = TOKEN_DECIMALS.get(token_upper, 18)
            decimals_raw = raw.get("decimal")
            if decimals_raw is not None:
                if isinstance(decimals_raw, str) and decimals_raw.startswith("0x"):
                    decimals = int(decimals_raw, 16)
                else:
                    try:
                        decimals = int(decimals_raw)
                    except (TypeError, ValueError):
                        pass
        return raw_int / (10**decimals)

    # Fallback: top-level "value" - for USDC/USDT it is often RAW (integer), so divide by 10^6
    v = t.get("value")
    if v is not None and isinstance(v, (int, float)):
        v = float(v)
        if is_stablecoin_6:
            # If value looks like raw (integer or >= 1), treat as raw and divide by 10^6
            if v >= 1.0 or (isinstance(t.get("value"), int)):
                return v / 1_000_000
            # Else assume already human (e.g. 8.68)
            return v
        return v
    return 0.0


def _normalize_address(addr: Any) -> str:
    """Ensure 0x-prefixed full 40-char hex address for display."""
    if addr is None:
        return ""
    s = str(addr).strip()
    if s.startswith("0x") or s.startswith("0X"):
        s = s[2:]
    if len(s) > 40:
        s = s[:40]
    elif len(s) < 40:
        s = s.zfill(40)
    return "0x" + s.lower()


def fetch_transfers_for_intent(
    chain: Optional[str],
    token: Optional[str],
    timeframe: Optional[str],
    limit: Optional[int],
) -> Dict[str, Any]:
    """
    Fetch real on-chain transfer data from Alchemy based on parsed intent.

    Only Ethereum is supported (Alchemy Transfers API on mainnet).
    Returns { "ok": True, "transfers": [...], "chain": "ethereum" } or
    { "ok": False, "error": "..." }.
    """
    limit = limit or 10
    if chain and chain != "ethereum":
        return {
            "ok": False,
            "error": f"Real on-chain data is only available for Ethereum in this demo (requested: {chain}).",
            "transfers": [],
        }
    try:
        w3 = get_web3()
        current_block = w3.eth.block_number
        from_block, to_block = _block_range_for_timeframe(timeframe or "7 days", current_block)
    except Exception as e:
        return {"ok": False, "error": str(e), "transfers": []}

    # ETH = native transfers (external); others = ERC-20
    if token and token.upper() == "ETH":
        category = ["external"]
        contract_addresses = None
    else:
        category = ["erc20"]
        contract_addresses = None
        if token:
            addr = TOKEN_CONTRACTS_ETH.get(token.upper())
            if addr:
                contract_addresses = [addr]

    def _is_requested_token(t: Dict[str, Any]) -> bool:
        if not contract_addresses or not token:
            return True
        allowed_addrs = {a.lower() for a in contract_addresses}
        token_upper = token.upper()
        addr = (t.get("rawContract") or {}).get("address") or ""
        if addr and addr.lower() in allowed_addrs:
            return True
        return (t.get("asset") or "").upper() == token_upper

    def _transfer_key(t: Dict[str, Any]) -> tuple:
        return (t.get("hash"), t.get("from"), t.get("to"), _transfer_value(t, token))

    # Paginate until we have at least `limit` unique transfers for the requested token (or run out of pages)
    all_raw: List[Dict[str, Any]] = []
    page_key: Optional[str] = None
    max_pages = 15
    page_size = 1000
    try:
        for _ in range(max_pages):
            transfers_batch, page_key = _alchemy_get_asset_transfers(
                from_block=from_block,
                to_block=to_block,
                category=category,
                max_count=page_size,
                contract_addresses=contract_addresses,
                order="desc",
                page_key=page_key,
            )
            all_raw.extend(transfers_batch)
            # After each page: filter to token, dedupe, and check if we have enough
            filtered = [t for t in all_raw if _is_requested_token(t)]
            seen: set = set()
            unique_raw: List[Dict[str, Any]] = []
            for t in filtered:
                k = _transfer_key(t)
                if k in seen:
                    continue
                seen.add(k)
                unique_raw.append(t)
            if len(unique_raw) >= limit:
                break
            if not page_key or len(transfers_batch) < page_size:
                break
    except Exception as e:
        return {"ok": False, "error": str(e), "transfers": []}

    # Final filter and dedupe (in case we didn't do it in loop for last batch)
    all_raw = [t for t in all_raw if _is_requested_token(t)]
    seen = set()
    unique_raw = []
    for t in all_raw:
        k = _transfer_key(t)
        if k in seen:
            continue
        seen.add(k)
        unique_raw.append(t)

    # Sort by value (desc) and take top `limit`
    sorted_transfers = sorted(unique_raw, key=lambda t: _transfer_value(t, token), reverse=True)[:limit]

    token_display = (token or "ETH").upper()
    decimals_round = 6 if token_display in ("USDC", "USDT") else 4

    rows: List[Dict[str, Any]] = []
    for t in sorted_transfers:
        meta = t.get("metadata") or {}
        block_num = t.get("blockNum")
        if isinstance(block_num, str) and block_num.startswith("0x"):
            block_number = int(block_num, 16)
        else:
            block_number = block_num if isinstance(block_num, int) else 0
        amount = _transfer_value(t, token)
        h = t.get("hash")
        if isinstance(h, str) and not h.startswith("0x"):
            h = "0x" + h
        if isinstance(h, str):
            h = h.lower()
        rows.append({
            "block_time": meta.get("blockTimestamp"),
            "block_number": block_number,
            "tx_hash": h or "",
            "from_address": _normalize_address(t.get("from")),
            "to_address": _normalize_address(t.get("to")),
            "amount": round(amount, decimals_round),
            "token_symbol": token_display,
        })
    return {"ok": True, "transfers": rows, "chain": "ethereum"}

