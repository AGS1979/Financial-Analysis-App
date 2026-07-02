"""Outbound HTTP helpers.

Every external HTTP call in the app should go through ``http_post`` / ``http_get``
rather than calling ``requests`` directly. They apply a default timeout (so a hung
external service can never freeze the Streamlit session) and retry with backoff on
transient failures, using a single shared ``requests.Session``.
"""

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover - older urllib3 layout
    from requests.packages.urllib3.util.retry import Retry

# Default timeout (seconds) applied to every outbound HTTP call.
DEFAULT_HTTP_TIMEOUT = 60


def _build_http_session():
    """A requests.Session with retry/backoff for transient failures on GET and POST."""
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1.5,  # 0s, 1.5s, 3s, 6s between attempts
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_HTTP_SESSION = _build_http_session()


def http_post(url, **kwargs):
    """requests.post with a default timeout and retry/backoff (see _build_http_session)."""
    kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
    return _HTTP_SESSION.post(url, **kwargs)


def http_get(url, **kwargs):
    """requests.get with a default timeout and retry/backoff (see _build_http_session)."""
    kwargs.setdefault("timeout", DEFAULT_HTTP_TIMEOUT)
    return _HTTP_SESSION.get(url, **kwargs)
