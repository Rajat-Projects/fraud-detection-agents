"""
Token-bucket style rate limiter using a sliding window.

Tracks request timestamps per identifier (API key, IP, session ID) and
rejects requests that exceed the configured limit within the window.
Uses in-process memory — suitable for single-process deployments (Streamlit).
For multi-process production deployments, back this with Redis.
"""

import time
from collections import defaultdict


class RateLimiter:

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # {identifier: [timestamp, ...]}
        self._timestamps: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """
        Check whether the identifier is within its rate limit.

        Slides the window by discarding timestamps older than window_seconds,
        then counts what remains. If count < max_requests, the request is
        recorded and allowed; otherwise it is rejected.

        Returns:
            (allowed: bool, info: dict)
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Slide the window — discard expired timestamps
        self._timestamps[identifier] = [
            ts for ts in self._timestamps[identifier] if ts > window_start
        ]

        current_count = len(self._timestamps[identifier])

        if current_count >= self.max_requests:
            oldest = self._timestamps[identifier][0]
            reset_in = int(oldest + self.window_seconds - now) + 1
            return False, {
                "allowed": False,
                "current_count": current_count,
                "limit": self.max_requests,
                "remaining": 0,
                "reset_in_seconds": max(reset_in, 0),
            }

        self._timestamps[identifier].append(now)
        return True, {
            "allowed": True,
            "current_count": current_count + 1,
            "limit": self.max_requests,
            "remaining": self.max_requests - (current_count + 1),
        }
