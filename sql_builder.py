from typing import Tuple

from .schemas import QueryIntent


def _dataset_for_metric(metric: str) -> Tuple[str, str]:
    """
    Map a high-level metric to a dataset name and a default ORDER BY column.
    """
    if metric == "transfers":
        return "token_transfers", "amount"
    if metric == "dex_trades":
        return "dex_trades", "amount"
    # wallet_activity and transactions both map to the generic transactions dataset
    return "transactions", "value"


def _interval_literal(timeframe: str) -> str:
    """
    Convert a normalized timeframe like "7 days" into a SQL INTERVAL literal.
    """
    parts = timeframe.split()
    if len(parts) != 2:
        # Fallback to a safe default
        return "7 days"
    num, unit = parts
    try:
        int(num)
    except ValueError:
        return "7 days"

    if unit.startswith("day"):
        unit = "days"
    elif unit.startswith("hour"):
        unit = "hours"
    else:
        unit = "days"

    return f"{num} {unit}"


def build_sql(intent: QueryIntent) -> str:
    """
    Generate a simple SQL query that matches the inferred intent.

    This is intentionally generic "blockchain-style" SQL using Postgres-like
    INTERVAL syntax and common column names.
    """
    chain = intent.chain or "ethereum"
    dataset, order_column = _dataset_for_metric(intent.metric or "transfers")
    table = f"{chain}.{dataset}"

    interval = _interval_literal(intent.timeframe or "7 days")

    where_clauses = [f"block_time >= NOW() - INTERVAL '{interval}'"]

    # Token filter is only meaningful on token and DEX datasets
    if intent.token and dataset in {"token_transfers", "dex_trades"}:
        token_symbol = intent.token.replace("'", "''")
        where_clauses.append(f"token_symbol = '{token_symbol}'")

    where_sql = " AND\n".join(where_clauses)

    limit = intent.limit or 50

    # Basic column projection tailored per dataset
    if dataset == "token_transfers":
        select_cols = (
            "block_time,\n"
            "tx_hash,\n"
            "from_address,\n"
            "to_address,\n"
            "amount,\n"
            "token_symbol"
        )
    elif dataset == "dex_trades":
        select_cols = (
            "block_time,\n"
            "tx_hash,\n"
            "maker_address,\n"
            "taker_address,\n"
            "amount,\n"
            "token_symbol"
        )
    else:
        select_cols = (
            "block_time,\n"
            "tx_hash,\n"
            "from_address,\n"
            "to_address,\n"
            "value"
        )

    sql = (
        "SELECT\n"
        f"{select_cols}\n"
        f"FROM {table}\n"
        "WHERE "
        f"{where_sql}\n"
        f"ORDER BY {order_column} DESC\n"
        f"LIMIT {limit};"
    )

    return sql

