"""Timeout / retry / rate limit / circuit breaker — общая обвязка парсеров.

Время и ожидание — инъецируемые зависимости (RULES § 4.21): тесты подменяют
`clock`/`sleep` и не спят реальные секунды.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pricescope_core import StoreUnavailableError

T = TypeVar("T")
Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]

_TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}
_TRANSIENT_EXCEPTIONS = {
    "TimeoutException",
    "ConnectError",
    "ReadError",
    "RemoteProtocolError",
    "RequestError",
}


class RetryPolicy:
    """Политика повторов: 3 попытки, backoff 1/2/4 с + jitter ±20 %."""

    def __init__(
        self,
        attempts: int = 3,
        base_delay: float = 1.0,
        *,
        sleep: Sleep = asyncio.sleep,
        jitter: Callable[[], float] | None = None,
    ) -> None:
        self.attempts = attempts
        self.base_delay = base_delay
        self._sleep = sleep
        self._jitter = jitter or (lambda: random.uniform(0.8, 1.2))

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Выполнить операцию с повтором только на transient-ошибки."""
        last_exc: Exception | None = None
        for attempt in range(self.attempts):
            try:
                return await operation()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_exc = exc
                if not self._is_transient(exc) or attempt == self.attempts - 1:
                    raise
                delay = self.base_delay * (2**attempt) * self._jitter()
                await self._sleep(delay)
        raise StoreUnavailableError("Retry исчерпан") from last_exc

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        status = getattr(exc, "response", None)
        code = getattr(status, "status_code", None)
        return code in _TRANSIENT_STATUS or type(exc).__name__ in _TRANSIENT_EXCEPTIONS


class TokenBucketRateLimiter:
    """Ведёрко токенов: не более `rate` запросов в минуту."""

    def __init__(
        self,
        rate: int,
        *,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.rate = max(1, rate)
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(self.rate)
        self._updated = clock()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Ждать, пока появится токен."""
        async with self._lock:
            now = self._clock()
            self._tokens = min(
                self.rate, self._tokens + (now - self._updated) * self._rate_per_second
            )
            self._updated = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate_per_second
                await self._sleep(wait)
                self._tokens = 0
                self._updated = self._clock()
            else:
                self._tokens -= 1

    @property
    def _rate_per_second(self) -> float:
        """Токенов в секунду."""
        return self.rate / 60


class CircuitBreaker:
    """5 ошибок подряд → 5 минут skip; потом полуоткрытый пробный запрос."""

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 300.0,
        *,
        clock: Clock = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        """Открыт ли предохранитель в текущий момент."""
        if self._opened_at is None:
            return False
        if self._clock() - self._opened_at >= self.cooldown_seconds:
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def record_success(self) -> None:
        """Сбросить счётчик после успеха."""
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        """Учесть ошибку; при пороге — открыть предохранитель."""
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
