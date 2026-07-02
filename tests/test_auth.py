"""Password hashing/verification + session validation (with a mocked Supabase)."""

import hashlib
import types
from datetime import datetime, timedelta, timezone

from auth import session


# --------------------------------------------------------------------------- #
# Password hashing (bcrypt) + legacy SHA-256 migration path
# --------------------------------------------------------------------------- #
def test_bcrypt_roundtrip():
    h = session.hash_password("s3cret")
    assert session._is_bcrypt_hash(h)
    assert session.verify_password(h, "s3cret")
    assert not session.verify_password(h, "wrong")


def test_legacy_sha256_accepted_for_migration():
    legacy = hashlib.sha256("s3cret".encode()).hexdigest()
    assert not session._is_bcrypt_hash(legacy)
    # Legacy hashes must still verify (so the login flow can re-hash to bcrypt)...
    assert session.verify_password(legacy, "s3cret")
    # ...but a wrong password must not.
    assert not session.verify_password(legacy, "wrong")


def test_verify_empty_or_none_hash():
    assert not session.verify_password("", "x")
    assert not session.verify_password(None, "x")


def test_parse_timestamp():
    assert session._parse_timestamp(None) is None
    assert session._parse_timestamp("garbage") is None
    ts = session._parse_timestamp("2026-07-02T12:00:00+00:00")
    assert ts is not None and ts.tzinfo is not None
    # naive input is coerced to aware UTC
    naive = session._parse_timestamp("2026-07-02T12:00:00")
    assert naive is not None and naive.tzinfo is not None


# --------------------------------------------------------------------------- #
# validate_session with a mocked Supabase client + session_state
# --------------------------------------------------------------------------- #
class _Query:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def single(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._data)


class _Client:
    def __init__(self, data):
        self._data = data

    def table(self, name):
        return _Query(self._data)


def _fake_conn(row):
    return types.SimpleNamespace(client=_Client(row))


def _install_fake_st(monkeypatch, state):
    fake = types.SimpleNamespace(session_state=state, error=lambda *a, **k: None)
    monkeypatch.setattr(session, "st", fake)


def _future():
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


def _past():
    return (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()


def test_validate_session_valid(monkeypatch):
    monkeypatch.setattr(config_module(), "get_conn",
                        lambda: _fake_conn({"active_session_token": "tok",
                                            "session_expires_at": _future()}))
    _install_fake_st(monkeypatch, {"logged_in": True, "username": "u@x.com", "session_token": "tok"})
    assert session.validate_session() is True


def test_validate_session_token_mismatch(monkeypatch):
    monkeypatch.setattr(config_module(), "get_conn",
                        lambda: _fake_conn({"active_session_token": "SERVER",
                                            "session_expires_at": _future()}))
    _install_fake_st(monkeypatch, {"logged_in": True, "username": "u@x.com", "session_token": "LOCAL"})
    assert session.validate_session() is False


def test_validate_session_expired(monkeypatch):
    monkeypatch.setattr(config_module(), "get_conn",
                        lambda: _fake_conn({"active_session_token": "tok",
                                            "session_expires_at": _past()}))
    _install_fake_st(monkeypatch, {"logged_in": True, "username": "u@x.com", "session_token": "tok"})
    assert session.validate_session() is False


def test_validate_session_null_expiry_is_allowed(monkeypatch):
    # Rows created before the session_expires_at column existed have NULL -> treat as valid.
    monkeypatch.setattr(config_module(), "get_conn",
                        lambda: _fake_conn({"active_session_token": "tok",
                                            "session_expires_at": None}))
    _install_fake_st(monkeypatch, {"logged_in": True, "username": "u@x.com", "session_token": "tok"})
    assert session.validate_session() is True


def test_validate_session_not_logged_in(monkeypatch):
    _install_fake_st(monkeypatch, {"logged_in": False})
    assert session.validate_session() is False


def config_module():
    import config
    return config
