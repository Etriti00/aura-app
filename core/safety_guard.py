"""
Aura — Safety Guard
Human jitter algorithm, kill switch, request counter, and token cost tracking.
Ensures scraping behaves like a human and stops immediately when detection risk is high.
Thread-safe: all mutable counters protected by a lock.
"""

import random
import time
import threading
from datetime import datetime

from utils.logger import get_logger
from config import (
    JITTER_MIN, JITTER_MAX,
    READING_PAUSE_EVERY, READING_PAUSE_MIN, READING_PAUSE_MAX,
    BREAK_PAUSE_EVERY, BREAK_PAUSE_MIN, BREAK_PAUSE_MAX,
    KILL_SWITCH_CONSECUTIVE_FAILS, KILL_SWITCH_COOLDOWN_SECONDS,
)

logger = get_logger("safety_guard")


class SafetyGuard:
    """
    Manages scraping safety:
    - Human jitter delays between requests
    - Kill switch on consecutive failures (403/429/CAPTCHA)
    - Request counting and token cost accumulation
    All mutable state is protected by a threading.Lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.request_count = 0
        self.consecutive_fails = 0
        self.total_tokens_used = 0
        self.total_cost_usd = 0.0
        self._kill_switch_active = False
        self._kill_switch_activated_at = None
        self._cancelled = False

    def reset(self):
        """Reset counters for a new scraping session."""
        with self._lock:
            self.request_count = 0
            self.consecutive_fails = 0
            self._cancelled = False

    @property
    def is_killed(self) -> bool:
        """Check if the kill switch is currently active."""
        with self._lock:
            if not self._kill_switch_active:
                return False

            # Check if cooldown has elapsed
            if self._kill_switch_activated_at:
                elapsed = (datetime.now() - self._kill_switch_activated_at).total_seconds()
                if elapsed >= KILL_SWITCH_COOLDOWN_SECONDS:
                    self._kill_switch_active = False
                    self._kill_switch_activated_at = None
                    self.consecutive_fails = 0
                    logger.info("Kill switch cooldown expired. Scraping re-enabled.")
                    return False

            return True

    @property
    def cooldown_remaining_seconds(self) -> int:
        """Seconds remaining in kill switch cooldown."""
        with self._lock:
            if not self._kill_switch_active or not self._kill_switch_activated_at:
                return 0
            elapsed = (datetime.now() - self._kill_switch_activated_at).total_seconds()
            remaining = KILL_SWITCH_COOLDOWN_SECONDS - elapsed
            return max(0, int(remaining))

    def human_jitter(self, cancel_checker=None):
        """
        Apply human-like random delay between requests.
        Every N requests, apply longer 'reading' or 'break' pauses.
        """
        with self._lock:
            self.request_count += 1
            count = self.request_count

        # Break simulation (every 50 requests)
        if count % BREAK_PAUSE_EVERY == 0:
            delay = random.uniform(BREAK_PAUSE_MIN, BREAK_PAUSE_MAX)
            logger.info(f"Break simulation: pausing {delay:.0f}s after {count} requests")
            self._interruptible_sleep(delay, cancel_checker)
            return

        # Reading simulation (every 15 requests)
        if count % READING_PAUSE_EVERY == 0:
            delay = random.uniform(READING_PAUSE_MIN, READING_PAUSE_MAX)
            logger.info(f"Reading simulation: pausing {delay:.0f}s after {count} requests")
            self._interruptible_sleep(delay, cancel_checker)
            return

        # Normal jitter
        delay = random.uniform(JITTER_MIN, JITTER_MAX)
        logger.debug(f"Jitter: {delay:.1f}s (request #{count})")
        self._interruptible_sleep(delay, cancel_checker)

    def _interruptible_sleep(self, total_seconds: float, cancel_checker=None):
        """Sleep in small increments so we can check for cancellation.
        Does NOT hold the lock while sleeping."""
        elapsed = 0.0
        increment = 0.5  # Check cancellation every 0.5s
        while elapsed < total_seconds:
            if cancel_checker and cancel_checker():
                with self._lock:
                    self._cancelled = True
                return
            with self._lock:
                if self._cancelled:
                    return
            sleep_time = min(increment, total_seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time

    def report_success(self):
        """Report a successful request — resets consecutive failure counter."""
        with self._lock:
            self.consecutive_fails = 0

    def report_failure(self, status_code: int = 0, reason: str = ""):
        """
        Report a failed request. Triggers kill switch after N consecutive failures.
        Returns True if the kill switch was just activated.
        """
        with self._lock:
            self.consecutive_fails += 1
            logger.warning(
                f"Request failed (consecutive: {self.consecutive_fails}/"
                f"{KILL_SWITCH_CONSECUTIVE_FAILS}): "
                f"status={status_code}, reason={reason}"
            )

            if self.consecutive_fails >= KILL_SWITCH_CONSECUTIVE_FAILS:
                self._activate_kill_switch()
                return True
            return False

    def _activate_kill_switch(self):
        """Activate the kill switch. Must be called with self._lock held."""
        self._kill_switch_active = True
        self._kill_switch_activated_at = datetime.now()
        logger.critical(
            f"KILL SWITCH ACTIVATED — {KILL_SWITCH_CONSECUTIVE_FAILS} consecutive failures. "
            f"Scraping paused for {KILL_SWITCH_COOLDOWN_SECONDS // 60} minutes."
        )

    def add_token_usage(self, tokens: int, cost_usd: float):
        """Track cumulative token usage and cost."""
        with self._lock:
            self.total_tokens_used += tokens
            self.total_cost_usd += cost_usd

    def cancel(self):
        """Request cancellation of current operations."""
        with self._lock:
            self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled
