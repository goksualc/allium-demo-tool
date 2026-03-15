from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .parser import parse_prompt
from .schemas import QueryRequest, QueryResponse
from .sql_builder import build_sql
from .alchemy_client import get_latest_block_summary, fetch_transfers_for_intent


app = FastAPI(
    title="AskChain API",
    description="Natural language to blockchain SQL query generator",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/query", response_model=QueryResponse)
def create_query(payload: QueryRequest) -> QueryResponse:
    """
    Convert a natural language prompt into a parsed intent and SQL query.
    """
    intent = parse_prompt(payload.prompt)
    sql = build_sql(intent)
    return QueryResponse(intent=intent.to_dict(), sql=sql)


@app.post("/query/live")
def create_query_live(payload: QueryRequest) -> dict:
    """
    Same as /query but also fetches real on-chain transfer data from Alchemy
    when the parsed chain is Ethereum. Response includes intent, sql, and live_transfers.
    """
    intent = parse_prompt(payload.prompt)
    sql = build_sql(intent)
    result = fetch_transfers_for_intent(
        intent.chain,
        intent.token,
        intent.timeframe,
        intent.limit,
    )
    return {
        "intent": intent.to_dict(),
        "sql": sql,
        "live_transfers": result,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/eth/latest-block")
def latest_block() -> dict:
    """
    Simple demo endpoint that fetches the latest Ethereum block summary
    from Alchemy using your configured API key/URL.
    """
    return get_latest_block_summary()

