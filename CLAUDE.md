# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-page Streamlit application ("ARANC'AI'") that bundles ~15 financial-analysis "agents" behind email/password auth. The entire application lives in one file: **`app.py` (~7,850 lines)**. `utils.py` holds a single HTML-report helper; `test_pinecone.py` is a standalone connectivity script, not a test suite. There is currently **no automated test suite** and no lint/build tooling configured.

## Commands

```bash
# Run locally (requires secrets configured — see below)
streamlit run app.py

# Install dependencies
pip install -r requirements.txt

# Build/run the container (installs Chrome for plotly/kaleido image export)
docker build -t financial-analysis-app .
docker run -p 8501:8501 --env-file .env financial-analysis-app

# Manual Pinecone connectivity check (NOT a unit test)
python test_pinecone.py
```

The Dockerfile runs `streamlit run app.py --server.headless true` on Python 3.13-slim.

## Architecture

### Single-file monolith + router
`app.py` is structured as:
1. **Global init (top of file):** imports, one shared `AzureOpenAI` client (`openai_client`), `st.set_page_config`, a module-level Supabase connection `conn = st.connection("supabase", ...)`, and `logo_base64`.
2. **Auth + infra functions** (~lines 400–760): Supabase table accessors, `hash_password`/`verify_password`, `authentication_ui`, `validate_session`, `whitelist_manager_ui`, `log_audit_event`, `log_user_history`/`get_user_history`.
3. **One large function per agent** — e.g. `investment_memo_app()`, `dcf_agent_app()`, `special_situations_app()`, `esg_analyzer_app()`, `portfolio_agent_app()`, `pe_agent_app_azure()`, `agent_credit_app_azure()`, `commodity_forecasting_agent()`, `portfolio_risk_correlator_app()`, etc. Each renders its own Streamlit UI and owns its full interaction loop.
4. **`main()` (~line 7672):** the router. It gates on `authentication_ui()` + `validate_session()`, builds the sidebar agent list from permissions, and dispatches to the selected agent function via a large `if/elif` chain on `app_mode`.

**To add or modify an agent** you touch three places: the agent function itself, the `if/elif` router in `main()`, the `ALL_AGENT_DETAILS` card list in `main()`, **and** `config.toml` permissions (below). All four must use the exact same display string (e.g. `"DCF Ginny"`).

### Access control via `config.toml`
`config.toml` is a single `[user_permissions]` table mapping each user email to the list of agent display-names they may see. `"__DEFAULT__"` applies to anyone not listed. `main()` loads this at runtime and filters both the sidebar radio and the welcome-page cards. This is display-time gating only — there is no per-agent server-side enforcement beyond what's shown.

### Auth & sessions (Supabase)
Auth is Supabase Postgres tables accessed via `st_supabase_connection`, **not** Supabase Auth. Tables in use: `users`, `whitelist` (signup is whitelist-gated), `user_history`, `audit_log`, `credit_deals`, `tickers`. Single-session enforcement: each login writes an `active_session_token` to the `users` row; `validate_session()` invalidates a session if the stored token changes (i.e. login elsewhere logs you out). Passwords are hashed with **SHA-256** (`hashlib`).

### LLM & external services
There is no unified client wrapper — model/API calls are hand-rolled inside each agent, and most agents re-read env vars and re-create clients locally.
- **Azure OpenAI** — primary LLM (`openai_client` global, also re-instantiated in several agents).
- **DeepSeek** — called directly via `requests.post` in some agents (`DEEPSEEK_API_KEY`).
- **Google Vertex AI / Gemini + Google Document AI + DLP** — used by the PE agent (`pe_agent_app_azure`) for secure/confidential document handling.
- **Azure Document Intelligence** — PDF layout extraction (PE, Credit agents).
- **Document parsing:** PyMuPDF (`fitz`), pdfplumber, PyPDF2; HTML via BeautifulSoup; Word export via `python-docx`.
- **Embeddings / RAG:** `SentenceTransformer("all-MiniLM-L6-v2")` (384-dim) with **FAISS** local indexes (`.faiss` files, e.g. under `portfolio_agent_data/`) and **Pinecone** (index `portfolio-agent`).
- **Financial data:** FMP API (`FMP_API_KEY`), `yfinance`, EODHD (`EODHD_API_KEY`), Tavily (`TAVILY_API_KEY`) for news.
- **Commodity Forecaster:** Prophet + pandas-ta + Plotly (Chrome in the Docker image supports kaleido static export).

## Configuration & secrets

Secrets are read at runtime via `os.environ.get(...)`. Note: `st.connection("supabase")` additionally reads `.streamlit/secrets.toml` (`[connections.supabase]`) for the Supabase URL/key. Keys referenced across the app:

`AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_DI_ENDPOINT`, `AZURE_DI_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `FMP_API_KEY`, `EODHD_API_KEY`, `TAVILY_API_KEY`, `PINECONE_API_KEY`, `APP_ADMIN_PASSWORD`, plus Google Cloud service-account credentials for the PE agent.

`.gitignore` excludes `secrets.toml`, `.env`, `users.csv`, `whitelist.csv`, `*.docx`. **`test_pinecone.py` and `pinecone API.txt` contain a hardcoded Pinecone API key committed to the repo** — treat as a live secret; do not propagate it, and flag it if doing security work.

## SPEC.md — planned refactor (not yet done)

`SPEC.md` is a work order for a future refactor and is **aspirational, not the current state**. The package layout it describes (`auth/`, `agents/`, `llm/client.py`, `BaseAgent`, `config.py`) does **not** exist — everything is still in `app.py`. Its Phase 1 security items are also still open: SHA-256 (not bcrypt) hashing, `except KeyError` guarding `os.environ.get` (which never raises `KeyError`, so those blocks never fire), missing timeouts on `requests.post`, and non-expiring session tokens. Consult SPEC.md when asked to refactor or add agents; do not assume its target structure already exists.
