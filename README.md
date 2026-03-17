## AskChain — Natural Language Blockchain Query Tool

AskChain is a small developer tool that converts natural language questions
about blockchain activity into SQL-style queries over generic on-chain
datasets.

It is implemented in Python using FastAPI for the API layer, Streamlit for a
simple UI, and a lightweight regex / rule-based parser for intent detection.

For **what you can ask** (example questions, search by address/tx, chains), see
**[USAGE.md](../USAGE.md)**.

---

### How to install

1. Make sure you are using **Python 3.11**.
2. From the project root (the directory containing the `askchain` folder), create
   a virtual environment and install dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r askchain/requirements.txt
```

---

### How to run the FastAPI server

From the project root:

```bash
uvicorn askchain.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

#### Example request

`POST /query`

Request body:

```json
{
  "prompt": "largest USDC transfers on ethereum last 24 hours"
}
```

Example response shape:

```json
{
  "intent": {
    "chain": "ethereum",
    "token": "USDC",
    "metric": "transfers",
    "timeframe": "24 hours",
    "limit": 50
  },
  "sql": "SELECT ..."
}
```

You can also open the automatic docs:

- **OpenAPI / Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

---

### How to run the Streamlit UI

From the project root:

```bash
streamlit run askchain/app.py
```

The Streamlit app will open in your browser (by default at
`http://localhost:8501`). It provides:

- An input box: **"Ask a question about on-chain data"**
- A parsed intent preview
- The generated SQL query

Example prompt:

> show top 10 ETH transfers on base in the last 24 hours

---

### What you can ask (example questions)

AskChain understands **natural language** questions about on-chain activity. Include:

- **Chain** — say which chain (e.g. *on Ethereum*, *on Solana*).
- **Token** — which asset (e.g. *USDC*, *ETH*).
- **What you want** — e.g. *transfers*, *largest transfers*, *top transfers*.
- **Time** — e.g. *last 24 hours*, *last 7 days*, *past 3 days*.
- **How many** — e.g. *top 10*, *top 5*, *first 20*.

#### Example questions (copy and try)

**Ethereum (live data: from, to, amount)**

- *Show top 10 USDC transfers on Ethereum in the last 24 hours*
- *Largest ETH transfers on Ethereum in the last 7 days*
- *Top 20 USDC transfers on Ethereum past 3 days*

**Solana (signatures + slot/time; from/to/amount not available with Alchemy)**

- *Show top 10 USDC transfers on Solana in the last 24 hours*
- *Top USDC transfers on Solana last 7 days*

**Search by address or transaction (Ethereum only)**

- Paste an **Ethereum address** (e.g. `0x742d35Cc...`) and click **Run Query** → view balance and tx count.
- Paste a **transaction hash** (e.g. `0x5879f178...`) → view tx details (from, to, value, status).

You can also use the **example chips** below the search bar to fill the box, then click **Run Query**.

---

### Supported concepts (for parsing)

- **Chains**: `ethereum`, `solana`, `base`, `arbitrum`, `optimism`
- **Datasets** (via metric mapping):
  - `transfers` → `token_transfers`
  - `dex_trades` → `dex_trades`
  - `transactions` / `wallet_activity` → `transactions`
- **Timeframes**: phrases like `last 7 days`, `in the last 24 hours`,
  `past 3 days`, `7 days`, `24 hours`, etc.
- **Limits**: patterns like `top 5`, `top5`, `first 10`, or `limit 20`.
- **Token symbols**: uppercase words such as `USDC`, `ETH`, etc.

The goal is to provide a clear, inspectable starting point for
natural-language-to-SQL workflows over blockchain-style schemas.

---

### Optional: connect to real Ethereum data via Alchemy

AskChain ships with a small helper module `alchemy_client.py` that shows how to
connect to an Ethereum node hosted by Alchemy using `web3.py`.

1. Install the extra dependency (already listed in `requirements.txt`):

```bash
pip install -r askchain/requirements.txt
```

2. Create an app in the Alchemy dashboard and obtain either:

- A full HTTPS URL (e.g. `https://eth-mainnet.g.alchemy.com/v2/<YOUR_KEY>`) or
- Just the API key (`<YOUR_KEY>`).

3. Set one of these environment variables before running the API:

```bash
# Option 1: full URL
export ALCHEMY_HTTP_URL="https://eth-mainnet.g.alchemy.com/v2/<YOUR_KEY>"

# Option 2: API key only (mainnet)
export ALCHEMY_API_KEY="<YOUR_KEY>"
```

4. Start the FastAPI server as usual:

```bash
uvicorn askchain.main:app --reload
```

5. Call the demo endpoint to verify connectivity to Alchemy:

```bash
curl http://127.0.0.1:8000/eth/latest-block
```

You should see a small JSON payload with the latest block number, hash,
timestamp, and transaction count pulled from Ethereum mainnet via Alchemy.

---

### Optional: Solana live data via Alchemy

For Solana queries (e.g. "top 10 USDC transfers on Solana in the last 24 hours"),
the backend uses the Alchemy Solana RPC. **You need a separate Solana app** (your Ethereum app key will not work for Solana).

1. In the [Alchemy Dashboard](https://dashboard.alchemy.com), click **Create new app** and choose **Solana** as the chain (not Ethereum).
2. Open the app and copy its **HTTPS URL** (e.g. `https://solana-mainnet.g.alchemy.com/v2/abc123...`).
3. Set it in `askchain/solana_client.py` by editing the line:
   ```python
   _SOLANA_URL_DEFAULT = "https://solana-mainnet.g.alchemy.com/v2/YOUR_SOLANA_KEY"
   ```
   Or set the environment variable before starting the server:
   ```bash
   export ALCHEMY_SOLANA_HTTP_URL="https://solana-mainnet.g.alchemy.com/v2/your-solana-key"
   ```
4. Restart the FastAPI server. Solana queries will return recent transaction signatures (block time, slot, signature). Note: Alchemy Solana does not support `getParsedTransaction`, so from/to addresses and amounts are not available; for full transfer details use a provider like Helius.


# allium-demo-tool
