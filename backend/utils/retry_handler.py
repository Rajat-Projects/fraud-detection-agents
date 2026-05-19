"""
Exponential backoff retry handler with per-error-type routing.

Error handling philosophy:
  SecurityViolationError  — NEVER retry. A detected injection or policy
                            violation must halt immediately. Retrying would
                            pass the same malicious input through again.
  Rate limit errors       — Retry with full backoff. The API will accept
                            the request once the window resets.
  TimeoutError            — One quick retry (network blip), then full backoff.
  ValueError / KeyError   — One quick retry (schema mismatch from LLM), then
                            raise FallbackRequired so the pipeline can use a
                            deterministic fallback instead of silently failing.
  Any other exception     — Log the error TYPE (never the message), then
                            full backoff. After max_retries, raise FallbackRequired.

FallbackRequired carries the agent name so the pipeline orchestrator knows
exactly which agent needs its fallback path activated.
"""

import random
import time
from utils.logger import FraudPipelineLogger


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class SecurityViolationError(Exception):
    """Raised when a security check (injection, policy) detects a violation."""


class RateLimitError(Exception):
    """Raised when the LLM API returns a rate-limit response."""


class FallbackRequired(Exception):
    """
    Raised when retries are exhausted and the agent must use its fallback path.
    Carries agent_name so the orchestrator can route to the correct fallback.
    """

    def __init__(self, agent_name: str, reason: str):
        self.agent_name = agent_name
        self.reason = reason
        super().__init__(f"Fallback required for {agent_name}: {reason}")


# ---------------------------------------------------------------------------
# Retry handler
# ---------------------------------------------------------------------------

class RetryHandler:

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._logger = FraudPipelineLogger("retry_handler")

    def run_with_retry(self, func, *args, agent_name: str = "unknown", **kwargs):
        """
        Call func(*args, **kwargs) with per-error-type retry logic.

        Returns the function's return value on success.
        Raises SecurityViolationError immediately (no retry).
        Raises FallbackRequired after max_retries are exhausted.
        """
        last_exception: Exception = RuntimeError("no attempts made")

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)

            except SecurityViolationError:
                # Security violations are never retried — re-raise immediately.
                raise

            except Exception as exc:
                last_exception = exc
                error_type = type(exc).__name__

                # Rate limit — full exponential backoff, keep retrying
                if "rate" in str(exc).lower() or isinstance(exc, RateLimitError):
                    if attempt < self.max_retries:
                        delay = self._calculate_backoff(attempt)
                        self._logger.log_agent_error(agent_name, error_type)
                        time.sleep(delay)
                        continue

                # Timeout — one short retry, then backoff
                elif isinstance(exc, TimeoutError):
                    if attempt == 0:
                        time.sleep(0.5)
                        continue
                    elif attempt < self.max_retries:
                        delay = self._calculate_backoff(attempt)
                        time.sleep(delay)
                        continue

                # Schema / value errors — one short retry, then fallback
                elif isinstance(exc, (ValueError, KeyError)):
                    if attempt == 0:
                        time.sleep(0.5)
                        continue
                    else:
                        raise FallbackRequired(agent_name, error_type) from exc

                # All other exceptions — log type, backoff, retry
                else:
                    self._logger.log_agent_error(agent_name, error_type)
                    if attempt < self.max_retries:
                        delay = self._calculate_backoff(attempt)
                        time.sleep(delay)
                        continue

        raise FallbackRequired(agent_name, type(last_exception).__name__) from last_exception

    def _calculate_backoff(self, attempt: int) -> float:
        delay = self.base_delay * (2 ** attempt)
        jitter = random.uniform(0, delay * 0.1)
        return min(delay + jitter, self.max_delay)
