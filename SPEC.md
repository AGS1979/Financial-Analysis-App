# Financial-Analysis-App — Refactor & New Agents Spec

**Target repo:** `AGS1979/Financial-Analysis-App` (fork/clone locally)
**Purpose:** Hand this document to Claude Code as a work order. It covers two phases: (1) refactor the existing monolith into a maintainable package structure, (2) add new agents on top of the clean structure.

Give Claude Code this whole file as context and ask it to work phase by phase, committing after each phase so changes are reviewable and revertible.

---

## Phase 0 — Safety net before touching anything

- Ensure `.env` / secrets are NOT committed. Confirm `.gitignore` covers `secrets.toml`, `.env`, `*.pem`.
- Create a `refactor` branch. Do not work on `master` directly.
- If there's no test coverage, ask Claude Code to write a handful of smoke tests first (e.g. "app imports without error," "login flow with mocked Supabase client," "memo generation with mocked DeepSeek response") so refactor steps can be verified.

## Phase 1 — Security fixes (do first, independent of restructuring)

1. **Replace SHA-256 password hashing with `bcrypt` (or `argon2-cffi`).**
   - Add a migration path: on next successful login with the old SHA-256 hash, re-hash with bcrypt and update the stored value. Don't force a mass password reset if avoidable.
2. **Fix the `os.environ.get(...)` + `except KeyError` pattern.** `os.environ.get` returns `None` on missing keys, it never raises `KeyError`. Replace with explicit `None` checks that fail loudly with a clear message, or switch to `os.environ[...]` (which does raise `KeyError`) inside the `try` block.
3. **Add timeouts and retry/backoff to all `requests.post` calls** (DeepSeek, FMP, etc.) — a hung external call currently can freeze the Streamlit session indefinitely.
4. **Add session token expiry.** Current sessions are valid forever until manually replaced. Add a `created_at`/`expires_at` column and check it in `validate_session()`.

## Phase 2 — Break up the monolith

Target structure:

```
financial_analysis_app/
  app.py                      # thin entrypoint: page config, routing between agents
  auth/
    __init__.py
    db.py                     # get_users_db, get_whitelist_db, add_user_db, etc.
    session.py                # hash_password, verify_password, validate_session, tokens
    ui.py                     # authentication_ui, whitelist_manager_ui
  agents/
    __init__.py
    base.py                   # shared Agent interface (see Phase 3)
    memo_agent.py             # investment_memo_app logic, refactored into a class
    qa_agent.py                # (if a Q&A agent exists further in the file — inspect and extract)
  llm/
    __init__.py
    client.py                 # unified LLMClient wrapping Azure OpenAI, DeepSeek, Vertex AI, OpenAI
  documents/
    __init__.py
    pdf.py                    # PyMuPDF/pdfplumber/PyPDF2 extraction helpers
    html_parse.py             # extract_text_from_html and friends
    docx_export.py            # save_sections_to_word and any other Word export
  utils/
    __init__.py
    text.py                   # clean_markdown, formatting helpers
    logging.py                # log_audit_event, log_user_history, get_user_history
  static/
    styles.py or styles.css   # the large CSS block currently inlined in app.py
  config.py                   # centralized env var loading with validation
```

Rules for this pass:
- Move code, don't rewrite logic yet — this phase is structural, not behavioral. Keep diffs reviewable.
- Every module gets docstrings explaining its role.
- `config.py` should load and validate all required env vars once at startup and raise a single clear error listing everything missing, rather than scattered `try/except` blocks throughout.
- The giant inline `st.markdown("""<style>...""")` CSS block should move to a separate file loaded once.

## Phase 3 — Common agent interface

Before adding new agents, define a shared interface so every agent (existing and new) plugs into the app the same way:

```python
# agents/base.py
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    name: str
    description: str

    @abstractmethod
    def render(self):
        """Render this agent's Streamlit UI and handle its interaction loop."""
        ...
```

`app.py` becomes a router: a sidebar/selectbox of registered agents, each calling `.render()`. This is what makes "add more agents" a low-friction operation going forward instead of another 1,000-line function bolted onto `app.py`.

Also standardize on the `llm/client.py` wrapper for all model calls, so agents don't each hand-roll their own `requests.post` or SDK client:

```python
class LLMClient:
    def complete(self, prompt: str, system: str = None, provider: str = "deepseek", **kwargs) -> str:
        ...
```

## Phase 4 — New agents to add

Pick and prioritize based on what the business actually needs — suggested set below, roughly in order of overlap with existing code (easiest to build on what's there):

1. **Earnings Call / Transcript Analysis Agent** — ingest an earnings call transcript (PDF/text), extract management tone, guidance changes, and analyst Q&A themes. Reuses the existing PDF/HTML extraction and DeepSeek summarization patterns almost directly.
2. **Peer Comparison Agent** — given a ticker or company name, pull comps (via `yfinance`, already a dependency) and generate a structured valuation comparison table + narrative. Extends the existing "Peer Comparison and Competitors" memo section into a standalone, reusable agent.
3. **Red-Flag / Risk Screening Agent** — scan a DRHP/10-K/annual report for governance, related-party transaction, and accounting red flags, using a structured checklist prompt rather than free-form generation, to reduce hallucination risk.
4. **Portfolio Monitoring Agent** — periodic (or on-demand) agent that ingests a portfolio (tickers + weights) and produces a digest of material news/filings since last run. This is more infrastructure-heavy (needs a scheduler or manual trigger) — sequence it later.
5. **Q&A-over-Document Agent** (if not already present later in the file — inspect lines beyond 1000 for this, since the memo generator references FAISS/embeddings which suggests a RAG Q&A feature already exists and may just need modularizing into the new `agents/` structure rather than building from scratch).

For each new agent, follow the same shape as `memo_agent.py` post-refactor: a class implementing `BaseAgent`, using `documents/` for parsing and `llm/client.py` for generation, with prompts kept in clearly separated constants (not buried inline) so they're easy to tune later.

## Phase 5 — Verification

- Re-run the smoke tests from Phase 0.
- Manually test: login, sign-up (whitelist-gated), memo generation end-to-end, at least one new agent end-to-end.
- Confirm no secrets in git history (`git log -p` scan or `git-secrets`/`trufflehog` if available).

---

## Notes for whoever runs this with Claude Code

- Work phase by phase, commit after each phase, and ask Claude Code to summarize what changed before moving to the next phase.
- Phase 1 (security) is independent and can be done even before the restructuring, if you want a quick win first.
- Only ~1,000 of the file's 7,854 lines were reviewed to produce this spec (GitHub blocks fetching the raw file outside a browser). Ask Claude Code to read the full file first and flag anything past line 1,000 that doesn't fit the structure above — there's likely at least one more agent (Q&A/RAG, given the FAISS/Pinecone/sentence-transformers imports) that isn't reflected here yet.
