"""Rate-limiting setup with a graceful fallback.

Uses `slowapi <https://github.com/laurentS/slowapi>`_ when it is installed
(the Docker image installs it via ``requirements.txt``). When it is absent,
a no-op limiter is provided so the application still imports and runs — the
``@limiter.limit(...)`` decorators become transparent pass-throughs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised in the container, not the unit tests
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
    RATE_LIMIT_AVAILABLE = True
except Exception:  # noqa: BLE001 - slowapi optional
    RATE_LIMIT_AVAILABLE = False
    RateLimitExceeded = None  # type: ignore[assignment,misc]

    class _NoopLimiter:
        """Fallback limiter whose ``limit`` decorator does nothing."""

        def limit(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    limiter = _NoopLimiter()  # type: ignore[assignment]
    logger.info("slowapi not installed; rate limiting disabled (no-op limiter).")
