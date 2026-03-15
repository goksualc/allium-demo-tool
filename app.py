from dataclasses import asdict

import streamlit as st

from askchain.parser import parse_prompt
from askchain.sql_builder import build_sql
from askchain.alchemy_client import fetch_transfers_for_intent


def _query_insights(intent) -> str:
    """Explain the query in simple language."""
    chain = (intent.chain or "ethereum").capitalize()
    token = intent.token or "tokens"
    metric = (intent.metric or "transfers").replace("_", " ")
    timeframe = intent.timeframe or "7 days"
    limit = intent.limit or 10
    return (
        f"This query returns the **top {limit} {metric}** for **{token}** on **{chain}** "
        f"in the **last {timeframe}**, ordered by amount (largest first). "
        "Results are live on-chain data from Ethereum."
    )


# Page config
st.set_page_config(
    page_title="AskChain — Query Blockchain Data",
    page_icon="◇",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS: dark Web3 aesthetic, glassmorphism, neon accents
st.markdown(
    """
    <style>
    /* Base */
    .stApp { background: linear-gradient(165deg, #0B0B12 0%, #12121F 40%, #0F0F1A 100%); }
    /* Hero */
    .askchain-hero { text-align: center; margin-bottom: 2rem; }
    .askchain-hero h1 {
        font-size: 1.85rem;
        font-weight: 700;
        background: linear-gradient(135deg, #E2E8F0 0%, #A5B4FC 50%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.35rem;
    }
    .askchain-hero p { color: #94A3B8; font-size: 1rem; margin-bottom: 1.5rem; }
    /* Glass card */
    .glass-card {
        background: rgba(26, 26, 46, 0.7);
        border: 1px solid rgba(139, 92, 246, 0.2);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 24px rgba(0,0,0,0.2);
    }
    .glass-card h3 {
        color: #A5B4FC;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
        letter-spacing: 0.02em;
    }
    /* Chips */
    .prompt-chip {
        display: inline-block;
        padding: 0.4rem 0.9rem;
        margin: 0.25rem;
        border-radius: 999px;
        background: rgba(139, 92, 246, 0.15);
        border: 1px solid rgba(139, 92, 246, 0.35);
        color: #C4B5FD;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .prompt-chip:hover {
        background: rgba(139, 92, 246, 0.25);
        border-color: rgba(139, 92, 246, 0.5);
    }
    /* Footer */
    .askchain-footer {
        text-align: center;
        color: #64748B;
        font-size: 0.8rem;
        margin-top: 2.5rem;
        padding: 1rem;
    }
    /* Dataframe container */
    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(139, 92, 246, 0.15);
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }
    /* Success message */
    .stSuccess { background: rgba(34, 197, 94, 0.12); border-radius: 8px; border: 1px solid rgba(34, 197, 94, 0.3); }
    </style>
    """,
    unsafe_allow_html=True,
)

# Hero
st.markdown(
    """
    <div class="askchain-hero">
        <h1>AskChain — Query Blockchain Data with Natural Language</h1>
        <p>Turn natural language into on-chain queries</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Search row: input + button
default_prompt = "Show top 10 USDC transfers on Ethereum in the last 24 hours"
input_value = st.session_state.get("prompt_from_chip") or st.session_state.get("last_prompt", default_prompt)
if st.session_state.get("prompt_from_chip"):
    del st.session_state["prompt_from_chip"]
col_input, col_btn = st.columns([5, 1])
with col_input:
    prompt = st.text_input(
        "Query",
        value=input_value,
        placeholder="Show top 10 USDC transfers on Ethereum in the last 24 hours",
        label_visibility="collapsed",
    )
st.session_state["last_prompt"] = prompt
with col_btn:
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    run_clicked = st.button("Run Query", type="primary", use_container_width=True)

# Example prompt chips
st.markdown("**Example prompts:**")
chip_cols = st.columns(4)
examples = [
    "Top Uniswap trades last 24h",
    "Most active wallets on Base",
    "Largest ETH transfers today",
    "Top 10 USDC transfers on Ethereum in the last 24 hours",
]
for col, label in zip(chip_cols, examples):
    with col:
        if st.button(label, key=f"chip_{label[:20]}", use_container_width=True):
            st.session_state["prompt_from_chip"] = label
            st.rerun()

# Run query
if run_clicked or st.session_state.get("fetch_live"):
    if not (prompt or "").strip():
        st.warning("Please enter a question.")
    else:
        intent = parse_prompt(prompt)
        sql = build_sql(intent)
        st.session_state["intent"] = intent
        st.session_state["sql"] = sql
        st.session_state["prompt_used"] = prompt
        st.session_state["fetch_live"] = True

# Main content: 2 columns when we have results
if "intent" in st.session_state and "sql" in st.session_state:
    intent = st.session_state["intent"]
    sql = st.session_state["sql"]
    prompt_used = st.session_state.get("prompt_used", "")

    if st.session_state.get("fetch_live"):
        with st.spinner("Fetching on-chain data…"):
            result = fetch_transfers_for_intent(
                intent.chain,
                intent.token,
                intent.timeframe,
                intent.limit,
            )
        st.session_state["fetch_live"] = False
        st.session_state["result"] = result
    else:
        result = st.session_state.get("result", {"ok": False, "transfers": []})

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### Results")
        if result.get("ok"):
            transfers = result.get("transfers") or []
            if transfers:
                st.success(
                    f"Showing the top {len(transfers)} {intent.token or 'transfer'} transfers by amount on "
                    f"{(intent.chain or 'ethereum').capitalize()} in the last {intent.timeframe}."
                )
                # Table with columns: block_time, block_number, tx_hash, from, to, amount
                df_display = transfers  # list of dicts with from_address, to_address, amount, etc.
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    column_config={
                        "block_time": st.column_config.TextColumn("block_time", width="medium"),
                        "block_number": st.column_config.NumberColumn("block_number", format="%d"),
                        "tx_hash": st.column_config.TextColumn("tx_hash", width="large"),
                        "from_address": st.column_config.TextColumn("from", width="large"),
                        "to_address": st.column_config.TextColumn("to", width="large"),
                        "amount": st.column_config.NumberColumn("amount", format="%.4f"),
                        "token_symbol": st.column_config.TextColumn("token_symbol", width="small"),
                    },
                    hide_index=True,
                )
            else:
                st.info("No transfers found for this query.")
        else:
            st.error(result.get("error", "Could not fetch data."))

    with col_right:
        # Card 1: Parsed Intent
        st.markdown(
            f"""
            <div class="glass-card">
                <h3>Parsed Intent</h3>
                <p style="color:#CBD5E1; font-size:0.9rem; margin:0; line-height:1.6;">
                    <strong>Chain:</strong> {(intent.chain or 'ethereum').capitalize()}<br/>
                    <strong>Token:</strong> {intent.token or '—'}<br/>
                    <strong>Metric:</strong> {(intent.metric or 'transfers').replace('_', ' ').title()}<br/>
                    <strong>Timeframe:</strong> Last {intent.timeframe or '7 days'}<br/>
                    <strong>Limit:</strong> {intent.limit or 10}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Card 2: Generated SQL
        st.markdown(
            """
            <div class="glass-card">
                <h3>Generated SQL</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(sql, language="sql")
        # Card 3: Query Insights
        st.markdown(
            """
            <div class="glass-card">
                <h3>Query Insights</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(_query_insights(intent))

# Footer
st.markdown(
    '<p class="askchain-footer">Powered by real on-chain data</p>',
    unsafe_allow_html=True,
)
