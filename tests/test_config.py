"""config.require_env — the fail-loud env-var validator."""

import pytest

import config


def test_require_env_returns_values(monkeypatch):
    monkeypatch.setenv("SMOKE_TEST_VAR", "hello")
    assert config.require_env("SMOKE_TEST_VAR") == {"SMOKE_TEST_VAR": "hello"}


def test_require_env_missing_stops_loudly(monkeypatch):
    errors = []
    monkeypatch.setattr(config.st, "error", lambda msg: errors.append(msg))

    def _stop():
        raise RuntimeError("st.stop called")

    monkeypatch.setattr(config.st, "stop", _stop)
    monkeypatch.delenv("DEFINITELY_MISSING_VAR_123", raising=False)

    with pytest.raises(RuntimeError, match="st.stop called"):
        config.require_env("DEFINITELY_MISSING_VAR_123")

    # The error message must name the missing variable.
    assert errors and "DEFINITELY_MISSING_VAR_123" in errors[0]


def test_require_env_reports_all_missing(monkeypatch):
    errors = []
    monkeypatch.setattr(config.st, "error", lambda msg: errors.append(msg))
    monkeypatch.setattr(config.st, "stop", lambda: (_ for _ in ()).throw(RuntimeError("stop")))
    monkeypatch.delenv("MISSING_A_1", raising=False)
    monkeypatch.delenv("MISSING_B_2", raising=False)

    with pytest.raises(RuntimeError):
        config.require_env("MISSING_A_1", "MISSING_B_2")

    assert "MISSING_A_1" in errors[0] and "MISSING_B_2" in errors[0]
