"""Shared utility helpers for the Financial-Analysis-App.

Submodules:
- ``net``      -- HTTP session with default timeout + retry/backoff (http_post/http_get)
- ``logging``  -- audit-log and user-history writers backed by Supabase
- ``branding`` -- logo loading / base64 encoding helpers
- ``report``   -- DCF HTML report formatting (``format_report_as_html``)

``format_report_as_html`` is re-exported here so the historical
``from utils import format_report_as_html`` import keeps working.
"""

from utils.report import format_report_as_html

__all__ = ["format_report_as_html"]
