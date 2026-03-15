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
    max_count: int = 100,
    contract_addresses: Optional[List[str]] = None,
    order: str = "desc",
) -> List[Dict[str, Any]]:
    """Call Alchemy Transfers API; returns list of transfer objects."""
    url = get_alchemy_url()
    params: Dict[str, Any] = {
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
        "category": category,
        "excludeZeroValue": True,
        "withMetadata": True,
        "maxCount": hex(min(max_count, 1000)),
        "order": order,
    }
    if contract_addresses:
        params["contractAddresses"] = [a.lower() for a in contract_addresses]
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
    return result.get("transfers") or []


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

    try:
        raw = _alchemy_get_asset_transfers(
            from_block=from_block,
            to_block=to_block,
            category=category,
            max_count=max(limit * 3, 50),  # fetch extra then sort by value
            contract_addresses=contract_addresses,
            order="desc",
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "transfers": []}

    # Normalize and sort by value desc, then take top `limit`
    def _value(t: Dict[str, Any]) -> float:
        v = t.get("value")
        return float(v) if v is not None else 0.0

    sorted_transfers = sorted(raw, key=_value, reverse=True)[:limit]

    rows: List[Dict[str, Any]] = []
    for t in sorted_transfers:
        meta = t.get("metadata") or {}
        rows.append({
            "block_time": meta.get("blockTimestamp"),
            "block_number": int(t.get("blockNum", "0x0"), 16) if isinstance(t.get("blockNum"), str) else t.get("blockNum"),
            "tx_hash": t.get("hash"),
            "from_address": t.get("from"),
            "to_address": t.get("to"),
            "amount": t.get("value"),
            "token_symbol": t.get("asset") or (token or "ETH"),
        })
    return {"ok": True, "transfers": rows, "chain": "ethereum"}

