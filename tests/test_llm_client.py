"""LLMClient — the unified model-call wrapper (deepseek + azure).

These cover the plumbing that Phase 3 migrated every agent onto, using mocked
transports so no live API is called (the SPEC's "mocked DeepSeek response" idea).
"""

import types

import pytest

import config
import llm.client as lc
from llm.client import LLMClient


class _Resp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": "MOCKED"}}]}


def _capturing_post(store):
    def _post(url, **kwargs):
        store["url"] = url
        store["kwargs"] = kwargs
        return _Resp()
    return _post


def test_deepseek_complete_builds_request(monkeypatch):
    store = {}
    monkeypatch.setattr(lc, "http_post", _capturing_post(store))
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "KEY")
    monkeypatch.setattr(config, "DEEPSEEK_API_URL", "http://deepseek.test")

    out = LLMClient().complete("hello", system="be nice", temperature=0.2)

    assert out == "MOCKED"
    assert store["url"] == "http://deepseek.test"
    assert store["kwargs"]["headers"]["Authorization"] == "Bearer KEY"
    payload = store["kwargs"]["json"]
    assert payload["model"] == "deepseek-chat"
    assert payload["messages"] == [
        {"role": "system", "content": "be nice"},
        {"role": "user", "content": "hello"},
    ]
    assert payload["temperature"] == 0.2


def test_deepseek_omits_temperature_when_absent(monkeypatch):
    store = {}
    monkeypatch.setattr(lc, "http_post", _capturing_post(store))
    LLMClient().chat([{"role": "user", "content": "hi"}])
    assert "temperature" not in store["kwargs"]["json"]


def test_deepseek_passes_response_format_and_timeout(monkeypatch):
    store = {}
    monkeypatch.setattr(lc, "http_post", _capturing_post(store))
    LLMClient().chat([{"role": "user", "content": "hi"}],
                     response_format={"type": "json_object"}, timeout=120)
    assert store["kwargs"]["json"]["response_format"] == {"type": "json_object"}
    assert store["kwargs"]["timeout"] == 120


def test_azure_chat_builds_request(monkeypatch):
    store = {}
    resp = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="AZURE_OK"))])

    class _Completions:
        def create(self, **kwargs):
            store.update(kwargs)
            return resp

    fake_client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=_Completions()))
    monkeypatch.setattr(config, "get_azure_client", lambda: fake_client)
    monkeypatch.setattr(config, "AZURE_OPENAI_DEPLOYMENT_NAME", "dep")

    out = LLMClient().chat([{"role": "user", "content": "x"}], provider="azure",
                           temperature=0.1, response_format={"type": "json_object"})

    assert out == "AZURE_OK"
    assert store["model"] == "dep"
    assert store["temperature"] == 0.1
    assert store["response_format"] == {"type": "json_object"}
    # max_tokens not passed -> must not appear
    assert "max_tokens" not in store


def test_azure_respects_explicit_model(monkeypatch):
    store = {}
    resp = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))])

    class _Completions:
        def create(self, **kwargs):
            store.update(kwargs)
            return resp

    monkeypatch.setattr(config, "get_azure_client",
                        lambda: types.SimpleNamespace(chat=types.SimpleNamespace(completions=_Completions())))
    LLMClient().chat([{"role": "user", "content": "x"}], provider="azure", model="gpt-4o")
    assert store["model"] == "gpt-4o"


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        LLMClient().chat([{"role": "user", "content": "x"}], provider="bogus")
