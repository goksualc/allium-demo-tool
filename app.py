from dataclasses import asdict

import streamlit as st

from askchain.parser import parse_prompt
from askchain.sql_builder import build_sql
from askchain.alchemy_client import get_latest_block_summary, fetch_transfers_for_intent


st.set_page_config(page_title="AskChain", layout="centered")

st.title("AskChain — Natural Language Blockchain Query Tool")

st.write(
    "Enter a natural language question about on-chain activity and AskChain "
    "will generate a SQL-style query against generic blockchain datasets."
)

default_prompt = (
    "show top 10 ETH transfers on base in the last 24 hours"
)

prompt = st.text_area(
    "Ask a question about on-chain data",
    value=default_prompt,
    height=120,
)

if st.button("Generate SQL"):
    if not prompt.strip():
        st.warning("Please enter a question first.")
    else:
        intent = parse_prompt(prompt)
        sql = build_sql(intent)
        st.session_state["intent"] = intent
        st.session_state["sql"] = sql

if "intent" in st.session_state and "sql" in st.session_state:
    intent = st.session_state["intent"]
    sql = st.session_state["sql"]
    st.subheader("Parsed intent")
    st.json(asdict(intent))
    st.subheader("Generated SQL")
    st.code(sql, language="sql")
    st.subheader("Real on-chain data (Alchemy)")
    st.caption(
        "Fetch live transfer data from Ethereum using your Alchemy API. "
        "Only Ethereum is supported for real data in this demo."
    )
    if st.button("Fetch real transfers", key="fetch_real"):
        with st.spinner("Calling Alchemy…"):
            result = fetch_transfers_for_intent(
                intent.chain,
                intent.token,
                intent.timeframe,
                intent.limit,
            )
        if result.get("ok"):
            transfers = result.get("transfers") or []
            if transfers:
                st.success(f"Found {len(transfers)} transfer(s) on Ethereum.")
                st.dataframe(transfers, use_container_width=True)
            else:
                st.info("No transfers found for this query.")
        else:
            st.error(result.get("error", "Unknown error"))

st.markdown("---")
st.subheader("Live Ethereum data (Alchemy demo)")
st.caption(
    "This section calls Alchemy directly from Streamlit to fetch the latest "
    "Ethereum block. Configure `ALCHEMY_HTTP_URL` in `alchemy_client.py`."
)

if st.button("Fetch latest Ethereum block"):
    try:
        summary = get_latest_block_summary()
        st.json(summary)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not fetch latest block from Alchemy: {exc}")
