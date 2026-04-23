"""In-process token-bucket style rate limiter keyed by client IP.

This is intentionally lightweight: the application is a single-process
service fronted by Nginx Proxy Manager, so a shared store is not required.
Privileged requests (see ``security.py``) bypass the limiter entirely.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status

from .config import settings
from .security import is_privileged


@dataclass
class _Window:
    minute: deque = field(default_factory=deque)
    hour: deque = field(default_factory=deque)


class RateLimiter:
    def __init__(self, per_minute: int, per_hour: int) -> None:
        self.per_minute = per_minute
        self.per_hour = per_hour
        self._buckets: dict[str, _Window] = {}
        self._lock = threading.Lock()
        self._last_cleanup = 0.0

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        stale = []
        for ip, window in self._buckets.items():
            while window.hour and now - window.hour[0] > 3600:
                window.hour.popleft()
            while window.minute and now - window.minute[0] > 60:
                window.minute.popleft()
            if not window.hour and not window.minute:
                stale.append(ip)
        for ip in stale:
            del self._buckets[ip]

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._cleanup(now)
            window = self._buckets.setdefault(key, _Window())
            while window.minute and now - window.minute[0] > 60:
                window.minute.popleft()
            while window.hour and now - window.hour[0] > 3600:
                window.hour.popleft()
            if len(window.minute) >= self.per_minute or len(window.hour) >= self.per_hour:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Try again later.",
                )
            window.minute.append(now)
            window.hour.append(now)


limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_hour)


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    if request.client is None:
        return "unknown"
    return request.client.host


def enforce(request: Request) -> None:
    if is_privileged(request):
        return
    limiter.check(client_ip(request))
