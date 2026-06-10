"""
Token-bucket rate limiter for VK API calls and uploads.

VK API rate limits (per group, per token):
  - messages.send:      ~20 RPS burst, ~5 RPS sustained
  - Other API methods:  ~3 RPS
  - Upload server calls:  ~2 RPS (photos/docs upload)
  - Media downloads:    no hard limit, but be gentle to VK CDN (~5 RPS)

Usage:
    limiter = RateLimiter(rate=5, burst=10)
    async with limiter:
        await api_call()

    # Or as decorator:
    @limiter.throttle
    async def send_message(): ...
"""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter.

    Allows *burst* requests immediately, then refills at *rate* tokens/second.
    """

    def __init__(self, rate: float, burst: int, name: str = ""):
        """
        Args:
            rate: Sustained rate in requests per second.
            burst: Maximum burst size (tokens available immediately).
            name: Label for debug logging.
        """
        self._rate = float(rate)
        self._burst = burst
        self._name = name
        self._tokens = float(burst)  # current token count
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._waiters = 0  # number of coroutines waiting

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            # Need to wait for a token
            deficit = 1.0 - self._tokens
            wait_time = deficit / self._rate

        await asyncio.sleep(wait_time)

        async with self._lock:
            self._refill()
            self._tokens -= 1.0

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def throttle(self, func):
        """Decorator: throttle an async function."""
        async def wrapper(*args, **kwargs):
            await self.acquire()
            return await func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        wrapper.__qualname__ = func.__qualname__
        return wrapper

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        pass


class VKRateLimiters:
    """Pre-configured rate limiters for different VK API operations.

    Based on VK API documentation and empirical testing:
    - messages.send: 20 RPS burst, 5 RPS sustained per token
    - Other API calls: 3 RPS burst/sustained per token
    - Upload operations: 2 RPS burst, 1 RPS sustained per token
    - Media downloads: 5 RPS shared
    """

    def __init__(self):
        # Send messages — most important, highest rate
        self.send = RateLimiter(rate=5.0, burst=20, name="vk-send")

        # General API calls (groups.getById, users.get, etc.)
        self.api = RateLimiter(rate=3.0, burst=5, name="vk-api")

        # Upload operations (getUploadServer + actual file upload)
        self.upload = RateLimiter(rate=1.0, burst=2, name="vk-upload")

        # Media downloads from VK CDN
        self.download = RateLimiter(rate=5.0, burst=10, name="vk-download")


# Global instance for the adapter
_default_limiters: Optional[VKRateLimiters] = None


def get_rate_limiters() -> VKRateLimiters:
    """Get or create the global VK rate limiters."""
    global _default_limiters
    if _default_limiters is None:
        _default_limiters = VKRateLimiters()
    return _default_limiters
