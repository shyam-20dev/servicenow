"""Tiny in-memory rate limiter + request-size guard (demo-grade, single process)."""
import time
from collections import defaultdict, deque

MAX_BODY_BYTES = 3 * 1024 * 1024  # 3 MB (uploads are further limited to 2 MB)


class RateLimiter:
    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        return True
