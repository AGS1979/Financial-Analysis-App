# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Streamlit application ("ARANC'AI'") that bundles 14 financial-analysis "agents" behind email/password auth. Originally a single ~7,850-line `app.py`; it has since been refactored (see **Refactor status** below) into a package: `app.py` is now a thin ~370-line router and the agents/auth/utils/config live in their own modules. There is a **pytest smoke-test suite** under `tests/` (see Commands); the root `conftest.py` stubs deployment-only heavy deps so it runs anywhere. No lint/build config beyond that; `py_compile` + `pyflakes` were also used during the refactor.

## Commands

```bash
# Run locally (requires secrets configured — see below)
streamlit run app.py

# Install dependencies
pip install -r requirements.txt

# Run the smoke-test suite (stubs heavy deps; no live services needed)
pip install -r requirements-dev.txt
python -m pytest

# Syntax + static checks also used during the refactor
python -m py_compile app.py config.py auth/*.py utils/*.py agents/*.py llm/*.py
python -m pyflakes app.py config.py auth/*.py utils/*.py agents/*.py llm/*.py   # watch for "undefined name"

# Build/run the container (installs Chrome for plotly/kaleido image export)
docker build -t financial-analysis-app .
docker run -p 8501:8501 --env-file .env financial-analysis-app
```

The Dockerfile runs `streamlit run app.py --server.headless true` on Python 3.13-slim.

## Architecture

### Package layout
```
app.py                # thin router: bootstrap + show_history_page + main()
config.py             # env vars, constants, require_env(), get_azure_client(), get_conn()
auth/  db.py          #   users/whitelist Supabase tables
       session.py     #   bcrypt hashing + validate_session (token + expiry)
       ui.py          #   login/sign-up + admin whitelist UI
utils/ net.py         #   http_post/http_get (default timeout + retry/backoff)
       logging.py     #   log_audit_event, log_user_history, get_user_history
       branding.py    #   logo load/encode helpers
       report.py      #   format_report_as_html (re-exported from utils/__init__)
agents/<name>.py      # one module per agent (see router in app.py)
static/styles.css     # the app stylesheet, injected once by app.py:_inject_css()
```

### app.py bootstrap + router
`app.py` runs, in order: `st.set_page_config` (must stay first Streamlit call) → `_inject_css()` (loads `static/styles.css`) → `config.validate_core_config()` → builds module globals `openai_client = config.get_azure_client()`, `conn = config.get_conn()`, and re-exports `DEEPSEEK_API_KEY`/`FMP_API_KEY`/`logo_base64` for the router to pass into agents. `main()` gates on `authentication_ui()` + `validate_session()`, builds the sidebar agent list from `config.toml` permissions, and dispatches via an `AgentRegistry` — `AGENTS.get(app_mode).render()` — built once by `_build_agent_registry()`. The registry (from `agents/base.py`: `BaseAgent`/`FunctionAgent`/`AgentRegistry`) is the single source of truth for both dispatch and the welcome-page cards.

**To add or modify an agent**:
1. write the agent as `agents/<name>.py` (a function that renders its own Streamlit UI) and import it in `app.py`;
2. register it in `_build_agent_registry()` via `add(name, title, description, render_fn)` — wrap any runtime args (client, keys, user id) in a lambda. This one entry drives both the router and the card;
3. add the display-name to `config.toml` `[user_permissions]`. All must use the exact same string (e.g. `"DCF Ginny"`).

Agents get shared dependencies by importing from `config`/`utils` (e.g. `from utils.net import http_post`, `from config import require_env`). A few agents (`dcf`, `real_time_sentinel`, `commodity`) receive the Azure `client` and/or API keys as **parameters** from the router rather than importing them.

### `config.py` vs `config.toml` (two different things)
- **`config.py`** — Python module: centralised env loading, `require_env()` (fails loudly listing every missing var; `os.environ.get` never raises), and lazy client/connection builders.
- **`config.toml`** — data file: a single `[user_permissions]` table mapping each user email to the agent display-names they may see (`"__DEFAULT__"` for everyone else). This is display-time gating only — no per-agent server-side enforcement.

### Auth & sessions (Supabase)
Auth is Supabase Postgres tables via `st_supabase_connection`, **not** Supabase Auth. Tables: `users`, `whitelist` (signup is whitelist-gated), `user_history`, `audit_log`, `credit_deals`, `tickers`. Passwords are hashed with **bcrypt**; legacy SHA-256 hashes are still verified and transparently re-hashed to bcrypt on the next successful login. Single-session enforcement writes `active_session_token` to the `users` row; sessions also expire after `SESSION_TTL_HOURS` (12) — **this requires a `users.session_expires_at timestamptz` column** (a NULL is treated as "no expiry"). Auth code lives in `auth/`.

### LLM & external services
Model calls go through the unified `llm.client.LLMClient` (`from llm import llm`; then `llm.complete(prompt, system=..., provider=...)` or `llm.chat(messages, ...)`), which wraps DeepSeek (default), Azure OpenAI, and OpenAI behind one text-returning API. `temperature`/`max_tokens` are only sent when provided; `response_format` (JSON mode) and other kwargs pass through. All outbound HTTP still uses `utils.net.http_post`/`http_get` (60s timeout + retry/backoff). **Exceptions not on LLMClient:** `agents/commodity.py` keeps the raw Azure client for its function-calling (`tools=`) loop, which needs the raw response object; and Google Vertex/Gemini (PE agent) is not wrapped.
- **Azure OpenAI** — primary LLM (`config.get_azure_client()`; also re-instantiated in several agents).
- **DeepSeek** — memo, special_situations, portfolio, tariff, risk_correlator.
- **Google Vertex AI / Gemini + Document AI + DLP** — PE agent (`agents/pe.py`).
- **Azure Document Intelligence** — PE and Credit agents.
- **Document parsing:** PyMuPDF (`fitz`), pdfplumber, PyPDF2; HTML via BeautifulSoup; Word export via `python-docx`.
- **Embeddings / RAG:** `SentenceTransformer("all-MiniLM-L6-v2")` with **FAISS** (in-memory, `agents/investment_memo.py`) and **Pinecone** index `portfolio-agent` (`agents/portfolio.py`). Note: `portfolio_agent_data/*.faiss` on disk is **not** loaded by the code.
- **Financial data:** FMP (`FMP_API_KEY`), `yfinance`, EODHD (`EODHD_API_KEY`), Tavily (`TAVILY_API_KEY`).
- **Commodity Forecaster** (`agents/commodity.py`): Prophet + pandas-ta (imported for its `df.ta` accessor side-effect) + Plotly.

## Configuration & secrets

Env vars are read in `config.py`. `st.connection("supabase")` additionally reads `.streamlit/secrets.toml` (`[connections.supabase]`). Keys: `AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`, `AZURE_DI_ENDPOINT`, `AZURE_DI_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `FMP_API_KEY`, `EODHD_API_KEY`, `TAVILY_API_KEY`, `PINECONE_API_KEY`, `APP_ADMIN_PASSWORD`, plus Google Cloud service-account creds for the PE agent. `config.validate_core_config()` hard-fails at startup if the core set (Azure + DeepSeek + FMP) is missing.

`.gitignore` excludes `secrets.toml`, `.env`, `users.csv`, `whitelist.csv`, `*.docx`, `SPEC.md`. **`test_pinecone.py` and `pinecone API.txt` still contain a hardcoded Pinecone key (now rotated/invalid, but the string remains in those files and in git history)** — scrub both, and never reintroduce hardcoded keys.

## Refactor status (SPEC-driven)

The refactor is following the work order in `SPEC.md` (kept locally, untracked/gitignored):
- **Phase 0 (safety net) — done:** pytest smoke suite in `tests/` (imports, password/session, LLMClient, registry) with a dep-stubbing `conftest.py`.
- **Phase 1 (security) — done:** bcrypt + legacy migration, `require_env` replacing the broken `except KeyError` pattern, HTTP timeouts + retry, session expiry.
- **Phase 2 (break up the monolith) — done:** `config.py`, `auth/`, `utils/`, `static/styles.css`, and all 14 agents extracted to `agents/`. Moves were byte-for-byte; import headers were computed from each function's AST.
- **Phase 3 — done:** `agents/base.py` (`BaseAgent`/`FunctionAgent`/`AgentRegistry`), `llm/client.py` (`LLMClient`), the registry-driven router, and all agent model calls routed through `LLMClient` (except commodity's function-calling loop and the PE agent's Vertex/Gemini calls).
- **Phase 4+ (not yet done):** the new agents in SPEC Phase 4. Duplicated per-agent document-parsing/report helpers (e.g. `parse_pdf_with_azure_di`, `parse_excel_to_markdown`, `clean_markdown`, `generate_report_html_from_markdown`) were intentionally left in place and are candidates for consolidation into `documents/`/`utils/`. A few agents still hold now-unused local config (e.g. ideagen passes an unused `client` through nested functions) — harmless, cleanup-later.
