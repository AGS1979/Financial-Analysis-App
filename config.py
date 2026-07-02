"""Centralised configuration for the Financial-Analysis-App.

All environment-variable access, shared constants, and construction of the
long-lived external clients (Azure OpenAI, Supabase) live here so the rest of the
app imports validated values from a single place instead of scattering
``os.environ.get`` / client-init code across every agent.

Nothing in this module runs a Streamlit command at import time, so it is safe to
``import config`` before ``st.set_page_config`` is called. Validation and client
construction happen lazily via ``validate_core_config`` / ``get_azure_client`` /
``get_conn`` once the page is configured.
"""

import os

import streamlit as st
from openai import AzureOpenAI
from st_supabase_connection import SupabaseConnection

# --- Shared constants ---
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
AZURE_OPENAI_API_VERSION = "2024-02-01"
SESSION_TTL_HOURS = 12  # how long a login session stays valid before re-auth

# --- Environment variables (read once at import; None when unset) ---
AZURE_OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_DI_ENDPOINT = os.environ.get("AZURE_DI_ENDPOINT")
AZURE_DI_KEY = os.environ.get("AZURE_DI_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
FMP_API_KEY = os.environ.get("FMP_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")  # optional: app uses Azure OpenAI by default
EODHD_API_KEY = os.environ.get("EODHD_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
APP_ADMIN_PASSWORD = os.environ.get("APP_ADMIN_PASSWORD")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Variables required for the app to boot at all (global Azure client + core feeds).
# Per-agent extras (Azure DI, EODHD, Tavily, Pinecone, ...) are validated by each
# agent via require_env() when that agent runs.
_CORE_REQUIRED = [
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "DEEPSEEK_API_KEY",
    "FMP_API_KEY",
]

_openai_client = None


def require_env(*names):
    """Return the named environment variables as a dict, or stop the app with a clear
    message listing every one that is missing.

    ``os.environ.get`` returns ``None`` for missing keys (it never raises
    ``KeyError``), so missing configuration must be checked explicitly.
    """
    values = {name: os.environ.get(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        st.error(
            "Configuration error: the following required environment variable(s) are "
            f"missing or empty: {', '.join(missing)}. Please set them in your "
            "environment (or secrets.toml)."
        )
        st.stop()
    return values


def validate_core_config():
    """Validate the environment variables the app needs to start. Call once after
    ``st.set_page_config``."""
    require_env(*_CORE_REQUIRED)


def get_azure_client():
    """Return the shared AzureOpenAI client, constructing it once on first use."""
    global _openai_client
    if _openai_client is None:
        cfg = require_env(
            "AZURE_OPENAI_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT_NAME"
        )
        _openai_client = AzureOpenAI(
            api_key=cfg["AZURE_OPENAI_KEY"],
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=cfg["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=cfg["AZURE_OPENAI_DEPLOYMENT_NAME"],
        )
    return _openai_client


def get_conn():
    """Return the shared Supabase connection. ``st.connection`` caches per config, so
    repeated calls return the same underlying connection."""
    return st.connection("supabase", type=SupabaseConnection)
