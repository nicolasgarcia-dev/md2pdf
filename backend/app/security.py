"""Owner bypass token handling.

Requests that present a valid token in the ``X-Bypass-Token`` header or in
the ``md2pdf_bypass`` cookie are marked as privileged: they skip rate
limiting and use the larger ``OWNER_MAX_*`` size limits. The bypass is
transparent to normal visitors: no UI hints, no alternative routes.
"""

from __future__ import annotations

import hmac
from typing import Optional

from fastapi import Request

from .config import settings

BYPASS_COOKIE_NAME = "md2pdf_bypass"
BYPASS_HEADER_NAME = "X-Bypass-Token"


def _constant_time_equals(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def extract_token(request: Request) -> Optional[str]:
    header = request.headers.get(BYPASS_HEADER_NAME)
    if header:
        return header.strip()
    cookie = request.cookies.get(BYPASS_COOKIE_NAME)
    if cookie:
        return cookie.strip()
    # Allow a one-shot activation via query string so that the owner can
    # bookmark a URL that primes the cookie. The value itself is never
    # reflected back to the page.
    qs = request.query_params.get("k")
    if qs:
        return qs.strip()
    return None


def is_privileged(request: Request) -> bool:
    token = settings.bypass_token
    if not token:
        return False
    supplied = extract_token(request)
    if not supplied:
        return False
    return _constant_time_equals(token, supplied)
