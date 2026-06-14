from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[datetime]] = {}
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=window_seconds)
        with self._lock:
            bucket = self._hits.get(key)
            if bucket is None:
                bucket = deque()
                self._hits[key] = bucket
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = int(
                    (
                        bucket[0] + timedelta(seconds=window_seconds) - now
                    ).total_seconds()
                )
                return RateLimitResult(False, max(retry_after, 1))
            bucket.append(now)
            return RateLimitResult(True, 0)
