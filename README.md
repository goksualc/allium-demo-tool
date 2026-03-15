## AskChain — Natural Language Blockchain Query Tool

AskChain is a small developer tool that converts natural language questions
about blockchain activity into SQL-style queries over generic on-chain
datasets.

It is implemented in Python using FastAPI for the API layer, Streamlit for a
simple UI, and a lightweight regex / rule-based parser for intent detection.

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

### Supported concepts

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


# allium-demo-tool
