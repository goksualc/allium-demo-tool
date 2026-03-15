from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from pydantic import BaseModel


SUPPORTED_CHAINS = ["ethereum", "solana", "base", "arbitrum", "optimism"]


@dataclass
class QueryIntent:
    """
    Parsed representation of a natural-language blockchain query.

    This structure is intentionally minimal and generic so it can be
    reused across both the API layer and the Streamlit UI.
    """

    chain: Optional[str] = None
    token: Optional[str] = None
    metric: Optional[str] = None
    timeframe: Optional[str] = None
    limit: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class QueryRequest(BaseModel):
    """Incoming API payload."""

    prompt: str


class QueryResponse(BaseModel):
    """API response containing the parsed intent and generated SQL."""

    intent: Dict[str, Any]
    sql: str

