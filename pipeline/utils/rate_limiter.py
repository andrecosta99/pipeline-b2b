"""Rate limiter configuravel: espera um intervalo aleatorio entre min e max segundos."""
from __future__ import annotations

import random
import time

from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    def __init__(self, min_seconds: float, max_seconds: float):
        if min_seconds < 0 or max_seconds < min_seconds:
            raise ValueError("Intervalo de rate limiting invalido: min deve ser >= 0 e <= max")
        self.min_seconds = min_seconds
        self.max_seconds = max_seconds
        self._last_wait: float | None = None

    def wait(self) -> float:
        """Bloqueia durante um intervalo aleatorio em [min_seconds, max_seconds]."""
        delay = random.uniform(self.min_seconds, self.max_seconds)
        logger.debug("Rate limit: a aguardar %.2fs", delay)
        time.sleep(delay)
        self._last_wait = delay
        return delay
