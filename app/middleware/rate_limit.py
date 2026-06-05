"""In-memory sliding-window rate limiter for ``POST /api/chat`` (Phase 9)."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class ChatRateLimiter:
    """Per-client sliding window limiter (AP-04, SE-01, SE-05)."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, client_key: str) -> bool:
        if self.max_requests <= 0:
            return True
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            recent = [t for t in self._hits[client_key] if t > cutoff]
            if len(recent) >= self.max_requests:
                self._hits[client_key] = recent
                return False
            recent.append(now)
            self._hits[client_key] = recent
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_limiter: ChatRateLimiter | None = None


def get_chat_rate_limiter(max_requests: int, window_seconds: int = 60) -> ChatRateLimiter:
    global _limiter
    if _limiter is None or _limiter.max_requests != max_requests:
        _limiter = ChatRateLimiter(max_requests, window_seconds)
    return _limiter


def reset_chat_rate_limiter() -> None:
    global _limiter
    if _limiter is not None:
        _limiter.reset()
    _limiter = None
