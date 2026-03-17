## AskChain Beginner Guide

This guide explains, in simple terms, **what AskChain is**, **how it works**, and **how
all the pieces fit together**. It assumes you are comfortable installing Python and
running commands in a terminal, but you do **not** need to be a blockchain or SQL
expert.

---

### 1. What is AskChain?

AskChain is a small developer tool that does **one core job**:

> Turn natural language questions about blockchain activity into SQL-style queries.

Examples of questions:

- "show me the top 5 USDC transfers on ethereum in the last 7 days"
- "largest ETH transfers on base in the last 24 hours"

**What you can ask (quick reference):**

- **Token transfers:** Include the **chain** (e.g. *on Ethereum*, *on Solana*), **token** (USDC, ETH, etc.), **timeframe** (*last 24 hours*, *last 7 days*), and **limit** (*top 10*, *top 5*). Example: *Show top 10 USDC transfers on Ethereum in the last 24 hours*.
- **Search by address or transaction (Ethereum only):** In the dashboard, paste an Ethereum address or transaction hash and click Run Query to see balance/tx count or tx details (from, to, value, status).

AskChain:

1. **Understands your question** (chain, token, timeframe, etc.).
2. **Builds a SQL query string** that could be run against a blockchain data
   warehouse.
3. Optionally **connects to Ethereum via Alchemy** to show you the latest block
   so you know you are talking to a real chain.

AskChain does **not** directly query a big on-chain database yet. It focuses on
the "natural language → SQL" part of the pipeline and gives one simple live
blockchain example via Alchemy.

---

### 2. High‑level architecture

At a high level there are three layers:

- **UI (Streamlit):**
  - A simple web page where you can type questions and see results.
- **API / Logic (FastAPI + Python modules):**
  - Functions that parse your question and build SQL.
- **Blockchain connectivity (Alchemy + Web3):**
  - A helper that talks to the Ethereum network to fetch the latest block.

Everything lives under the `askchain/` folder.

---

### 3. Code layout (files and responsibilities)

- **`main.py`**
  - FastAPI application (backend API).
  - Exposes:
    - `POST /query` — parse a prompt and return `{ intent, sql }`.
    - `GET /eth/latest-block` — return latest Ethereum block via Alchemy.

- **`app.py`**
  - Streamlit app (frontend UI).
  - Lets you:
    - Enter a natural language question.
    - See the parsed intent and generated SQL.
    - Click a button to fetch the latest Ethereum block from Alchemy and show it.

- **`parser.py`**
  - Core **rule-based parser** for natural language.
  - Uses regular expressions and keyword matching to extract:
    - `chain` (ethereum, solana, base, arbitrum, optimism)
    - `token` (e.g. USDC, ETH)
    - `metric` (transfers, transactions, dex trades, etc.)
    - `timeframe` (e.g. "7 days", "24 hours")
    - `limit` (e.g. "top 10")
  - It does **not** use any external AI model; it is fully deterministic.

- **`sql_builder.py`**
  - Converts the `intent` into a SQL-style string.
  - Chooses a dataset based on the metric:
    - `transfers` → `token_transfers`
    - `dex_trades` → `dex_trades`
    - `transactions` → `transactions`
  - Builds a query like:

    ```sql
    SELECT
      block_time,
      tx_hash,
      from_address,
      to_address,
      amount,
      token_symbol
    FROM base.token_transfers
    WHERE block_time >= NOW() - INTERVAL '24 hours'
      AND token_symbol = 'ETH'
    ORDER BY amount DESC
    LIMIT 10;
    ```

- **`schemas.py`**
  - Defines small data structures for the app:
    - `QueryIntent` (Python dataclass) — holds `chain`, `token`, `metric`,
      `timeframe`, `limit`.
    - Pydantic models for the FastAPI request and response.

- **`alchemy_client.py`**
  - Simple wrapper around **Web3 + Alchemy**.
  - You paste your Alchemy URL into:

    ```python
    ALCHEMY_HTTP_URL: str = "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"
    ```

  - Provides:
    - `get_web3()` — returns a connected `Web3` client.
    - `get_latest_block_summary()` — returns the latest block number, hash,
      timestamp, and transaction count.

- **`requirements.txt`**
  - List of Python dependencies:
    - `fastapi`, `uvicorn`, `streamlit`, `python-dateutil`, `web3`, etc.

- **`README.md`**
  - Original installation and usage instructions.

- **`BEGINNER_GUIDE.md` (this file)**
  - Conceptual overview and explanations for beginners.

---

### 4. Data flow: from question to SQL

When you use the **Streamlit UI**:

1. You type a question like:

   > show top 10 ETH transfers on base in the last 24 hours

2. Streamlit calls `parse_prompt(prompt)`:
   - Detects:
     - `chain`: `"base"`
     - `token`: `"ETH"`
     - `metric`: `"transfers"`
     - `timeframe`: `"24 hours"`
     - `limit`: `10`
   - Wraps this into a `QueryIntent` dataclass.

3. Streamlit passes the `QueryIntent` to `build_sql(intent)`:
   - Chooses `base.token_transfers` as the table.
   - Builds a SQL string that filters by timeframe and token, and orders by
     amount, with a limit of 10.

4. Streamlit shows:
   - The parsed intent as JSON.
   - The generated SQL in a code block.

When you use the **FastAPI `/query` endpoint**:

1. You send a JSON body with `"prompt": "..."`.
2. FastAPI does the same steps internally:
   - Parse → build SQL.
3. It returns a JSON response with `intent` and `sql`.

> Note: At this stage, AskChain does **not** run that SQL against a real
> database. It generates the query string you could use against a blockchain
> data warehouse.

---

### 5. Where does real blockchain data come in?

Right now, there is **one concrete place** that talks to the real Ethereum
network: Alchemy.

- The **FastAPI endpoint** `GET /eth/latest-block`:
  - Calls `get_latest_block_summary()` in `alchemy_client.py`.
  - Returns live data from Ethereum mainnet.

- The **Streamlit UI**:
  - Has a button "Fetch latest Ethereum block".
  - When you click it, Streamlit calls the same helper and shows the JSON.

Think of it as a **sanity check**:

- "Is my app really connected to Ethereum?"
- "Can I see live block numbers changing?"

To fully connect the natural-language-to-SQL part to real data, you would
typically:

1. Set up a blockchain data warehouse (e.g. Postgres, ClickHouse, BigQuery) that
   has tables like `ethereum.token_transfers`.
2. Take the SQL generated by AskChain and run it against that database.
3. Return the query results to the UI.

That full pipeline is outside this MVP, but AskChain is designed so that step is
easy to add.

---

### 6. How the different servers relate

There are **two separate processes** you might run:

- **FastAPI server (backend API)**

  ```bash
  cd /Users/goksualcinkaya/allium_demo_tool
  source askchain/.venv/bin/activate
  python -m uvicorn askchain.main:app --reload
  ```

  - Lives at `http://127.0.0.1:8000`
  - Handles:
    - `POST /query`
    - `GET /eth/latest-block`

- **Streamlit app (frontend UI)**

  ```bash
  cd /Users/goksualcinkaya/allium_demo_tool
  source askchain/.venv/bin/activate
  python -m streamlit run askchain/app.py
  ```

  - Lives at `http://localhost:8501`
  - Provides:
    - Text box for natural language questions.
    - Display for parsed intent and SQL.
    - Button to fetch latest Ethereum block.

They are independent but share the same **core parsing and SQL-building logic**.

---

### 7. How to extend this project

Some ideas for next steps:

- **Support more natural language patterns**
  - e.g. "last week", "yesterday", "since Monday", "between two dates".
  - Add more regex + rules to `parser.py`.

- **Add more metrics / datasets**
  - NFT trades, lending protocol events, bridge transfers, etc.
  - Map new metrics to new datasets in `sql_builder.py`.

- **Connect to a real database**
  - Add a database client (e.g. `asyncpg`, `psycopg2`, or SQLAlchemy).
  - Create tables matching the schemas used in the SQL.
  - Add a new endpoint or Streamlit section that actually runs the SQL and
    displays rows.

- **Improve the UI**
  - Add presets ("Top token transfers", "Whale activity", etc.).
  - Add charts for volumes over time.

The current structure (clear parser, SQL builder, schemas, API, UI, and
Alchemy helper) is intentionally simple so you can grow it in whatever direction
you prefer.

