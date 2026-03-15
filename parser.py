import re
from typing import Optional

from .schemas import QueryIntent, SUPPORTED_CHAINS


TOKEN_PATTERN = re.compile(r"\b([A-Z]{2,10})\b")


def _parse_chain(prompt: str) -> Optional[str]:
    text = prompt.lower()
    for chain in SUPPORTED_CHAINS:
        if chain in text:
            return chain
    return None


def _parse_timeframe(prompt: str) -> Optional[str]:
    """
    Extract a relative timeframe like "7 days" or "24 hours".
    """
    text = prompt.lower()

    # Patterns like "last 7 days", "in the last 24 hours", "past 3 days"
    match = re.search(
        r"(last|past|in the last)\s+(\d+)\s*(day|days|d|hour|hours|h)", text
    )
    if not match:
        # Fallback: bare "7 days", "24h", etc.
        match = re.search(r"\b(\d+)\s*(day|days|d|hour|hours|h)\b", text)

    if not match:
        return None

    num = int(match.group(2) if len(match.groups()) >= 3 else match.group(1))
    unit_raw = match.group(3) if len(match.groups()) >= 3 else match.group(2)

    if unit_raw.startswith("d"):
        unit = "days"
    else:
        unit = "hours"

    return f"{num} {unit}"


def _parse_limit(prompt: str) -> Optional[int]:
    text = prompt.lower()

    # "top 5", "top5"
    match = re.search(r"top\s*(\d+)", text)
    if match:
        return int(match.group(1))

    # "first 10"
    match = re.search(r"first\s+(\d+)", text)
    if match:
        return int(match.group(1))

    # Explicit "limit 20"
    match = re.search(r"limit\s+(\d+)", text)
    if match:
        return int(match.group(1))

    return None


def _parse_metric(prompt: str) -> Optional[str]:
    """
    Map natural language phrases to a high-level metric.

    Supported metrics:
    - transfers      -> token_transfers dataset
    - dex_trades     -> dex_trades dataset
    - transactions   -> transactions dataset
    - wallet_activity -> treated as transactions dataset
    """
    text = prompt.lower()

    if "transfer" in text or "sent" in text or "send" in text:
        return "transfers"

    if "swap" in text or "dex trade" in text or "dex trades" in text or "trade" in text:
        return "dex_trades"

    if "wallet activity" in text:
        return "wallet_activity"

    if "transaction" in text or "tx " in text or " txs" in text:
        return "transactions"

    # "top N" without explicit wording – default to transfers as a common case
    if "top" in text or "largest" in text or "biggest" in text:
        return "transfers"

    return None


def _parse_token(prompt: str, chain: Optional[str]) -> Optional[str]:
    """
    Detect a token symbol, assuming it is written in uppercase (e.g. USDC, ETH).
    """
    # Remove obvious non-token uppercase words we might add later.
    candidates = TOKEN_PATTERN.findall(prompt)
    if not candidates:
        return None

    # Basic heuristic: prefer symbols that are not obvious acronyms of chains.
    chain_aliases = {"ETH": "ethereum"}
    for symbol in candidates:
        if symbol in chain_aliases and (
            chain is None or chain_aliases[symbol] == chain
        ):
            return symbol

    # Otherwise just take the first candidate.
    return candidates[0]


def parse_prompt(prompt: str) -> QueryIntent:
    """
    Main entry point for natural language parsing.

    Uses simple regex and keyword-based rules to extract the core intent
    fields the rest of the system needs.
    """
    chain = _parse_chain(prompt)
    timeframe = _parse_timeframe(prompt)
    limit = _parse_limit(prompt)
    metric = _parse_metric(prompt)
    token = _parse_token(prompt, chain)

    # Reasonable defaults when not specified
    if metric is None:
        metric = "transfers"
    if timeframe is None:
        timeframe = "7 days"
    if limit is None:
        limit = 50

    return QueryIntent(
        chain=chain or "ethereum",
        token=token,
        metric=metric,
        timeframe=timeframe,
        limit=limit,
    )

