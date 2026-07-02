"""Smoke test: every core module and agent imports without error.

This is the runnable version of "app imports without error" — it catches broken
imports, undefined names, and bad module-level code across the whole package.
Deployment-only heavy deps are stubbed by the root conftest.py.
"""

import importlib

import pytest

CORE = [
    "config",
    "auth.db", "auth.session", "auth.ui",
    "utils.net", "utils.logging", "utils.branding", "utils.report",
    "llm", "llm.client",
    "agents.base",
]

AGENTS = [
    "agents.commodity", "agents.credit", "agents.dcf", "agents.esg",
    "agents.ideagen", "agents.investment_memo", "agents.model_integrity",
    "agents.pe", "agents.portfolio", "agents.real_time_sentinel",
    "agents.risk_correlator", "agents.sentinel", "agents.special_situations",
    "agents.tariff",
]


@pytest.mark.parametrize("module", CORE + AGENTS)
def test_module_imports_without_error(module):
    importlib.import_module(module)


def test_app_module_imports(monkeypatch):
    """Import app.py itself, neutralising its start-up side effects (page config,
    client/connection construction, logo/CSS I/O) so it can run headless."""
    import sys
    import streamlit as st
    import config
    import utils.branding as branding

    monkeypatch.setattr(st, "set_page_config", lambda *a, **k: None)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(config, "validate_core_config", lambda: None)
    monkeypatch.setattr(config, "get_azure_client", lambda: object())
    monkeypatch.setattr(config, "get_conn", lambda: object())
    monkeypatch.setattr(branding, "get_base64_logo_image", lambda *a, **k: "b64")
    monkeypatch.setattr(branding, "load_logo", lambda *a, **k: object())

    sys.modules.pop("app", None)
    app = importlib.import_module("app")

    # The registry should have been built with every routed agent.
    assert "DCF Ginny" in app.AGENTS
    assert app.AGENTS.get("Agent Pre-IPO") is not None
