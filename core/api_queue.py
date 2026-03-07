"""
Aura — API Queue
Universal, rate-limit-aware request queue. Every external API call routes through
this class instead of making raw HTTP calls.
"""

import time
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import httpx

from config import API_BACKOFF_STEPS, APOLLO_RATE_PER_MINUTE, APOLLO_RATE_PER_HOUR, HUNTER_RATE_PER_MINUTE
from database.db_manager import DatabaseManager
from database.schema import ApiUsageLog
from utils.logger import get_logger

logger = get_logger("api_queue")

# Per-service rate limit configuration
SERVICE_LIMITS = {
    "apollo": {"per_minute": APOLLO_RATE_PER_MINUTE, "per_hour": APOLLO_RATE_PER_HOUR},
    "hunter": {"per_minute": HUNTER_RATE_PER_MINUTE, "per_hour": 500},
    "hubspot": {"per_minute": 100, "per_hour": 1000},
    "pipedrive": {"per_minute": 80, "per_hour": 800},
}


class APIQueue:
    """Thread-safe, rate-limit-aware API request queue with exponential backoff."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._lock = threading.Lock()

        # Per-service timestamps of recent calls (for rate counting)
        self._call_timestamps: Dict[str, deque] = {}

        # Per-service backoff state
        self._backoff_until: Dict[str, float] = {}

        # Per-service rate limit headers from last response
        self._rate_limit_headers: Dict[str, Dict[str, Any]] = {}

    def _get_timestamps(self, service: str) -> deque:
        if service not in self._call_timestamps:
            self._call_timestamps[service] = deque()
        return self._call_timestamps[service]

    def _prune_timestamps(self, service: str):
        """Remove timestamps older than 1 hour."""
        ts = self._get_timestamps(service)
        cutoff = time.time() - 3600
        while ts and ts[0] < cutoff:
            ts.popleft()

    def _count_calls(self, service: str, window_seconds: int) -> int:
        """Count calls within the given time window."""
        ts = self._get_timestamps(service)
        cutoff = time.time() - window_seconds
        return sum(1 for t in ts if t >= cutoff)

    def _check_rate_limit(self, service: str) -> Optional[float]:
        """Check if rate limit would be exceeded. Returns wait time in seconds, or None."""
        limits = SERVICE_LIMITS.get(service)
        if not limits:
            return None

        # Check backoff
        backoff = self._backoff_until.get(service, 0)
        if time.time() < backoff:
            return backoff - time.time()

        # Check per-minute limit
        per_min = limits.get("per_minute", 999)
        if self._count_calls(service, 60) >= per_min:
            return 60 - (time.time() - self._get_timestamps(service)[0]) + 0.5

        # Check per-hour limit
        per_hour = limits.get("per_hour", 9999)
        if self._count_calls(service, 3600) >= per_hour:
            return 3600 - (time.time() - self._get_timestamps(service)[0]) + 0.5

        # Check Hunter-specific header-based limits
        if service == "hunter":
            headers = self._rate_limit_headers.get(service, {})
            remaining = headers.get("remaining")
            reset_at = headers.get("reset_at")
            if remaining is not None and remaining <= 2 and reset_at:
                wait = reset_at - time.time()
                if wait > 0:
                    return wait

        return None

    def request(self, service: str, method: str, url: str,
                headers: Dict[str, str] = None, params: Dict = None,
                json_data: Dict = None, timeout: float = 30.0) -> dict:
        """
        Make a rate-limited HTTP request.

        Returns: {"success": bool, "data": response_json, "status_code": int,
                  "error": str|None, "rate_limited": bool, "retry_after": float}
        """
        with self._lock:
            self._prune_timestamps(service)

            # Check rate limits
            wait_time = self._check_rate_limit(service)
            if wait_time and wait_time > 0:
                logger.warning(f"[{service}] Rate limit — waiting {wait_time:.1f}s")
                return {
                    "success": False,
                    "data": None,
                    "status_code": 429,
                    "error": "rate_limited",
                    "rate_limited": True,
                    "retry_after": wait_time,
                }

        # Make the request with exponential backoff on 429
        backoff_steps = list(API_BACKOFF_STEPS)
        last_error = None

        for attempt in range(len(backoff_steps) + 1):
            try:
                response = httpx.request(
                    method=method,
                    url=url,
                    headers=headers or {},
                    params=params,
                    json=json_data,
                    timeout=timeout,
                )

                # Record the call timestamp
                with self._lock:
                    self._get_timestamps(service).append(time.time())

                # Parse rate limit headers (Hunter.io pattern)
                self._parse_rate_headers(service, response.headers)

                # Handle 429 — exponential backoff
                if response.status_code == 429:
                    if attempt < len(backoff_steps):
                        wait = backoff_steps[attempt]
                        logger.warning(
                            f"[{service}] 429 received — backoff {wait}s (attempt {attempt + 1})"
                        )
                        with self._lock:
                            self._backoff_until[service] = time.time() + wait
                        time.sleep(wait)
                        continue
                    else:
                        # All retries exhausted
                        with self._lock:
                            self._backoff_until[service] = time.time() + 60
                        self._log_usage(service, url, response.status_code, 0, 0.0)
                        return {
                            "success": False,
                            "data": None,
                            "status_code": 429,
                            "error": f"Rate limited after {len(backoff_steps)} retries",
                            "rate_limited": True,
                            "retry_after": 60,
                        }

                # Parse response
                try:
                    data = response.json()
                except Exception:
                    data = {"raw_text": response.text[:500]}

                # Log usage
                self._log_usage(service, url, response.status_code, 0, 0.0)

                return {
                    "success": 200 <= response.status_code < 300,
                    "data": data,
                    "status_code": response.status_code,
                    "error": None if 200 <= response.status_code < 300 else f"HTTP {response.status_code}",
                    "rate_limited": False,
                    "retry_after": 0,
                }

            except httpx.TimeoutException:
                last_error = "Request timed out"
                logger.warning(f"[{service}] Timeout on {url}")
            except httpx.ConnectError:
                last_error = "Connection failed"
                logger.warning(f"[{service}] Connection failed for {url}")
            except Exception as e:
                last_error = str(e)
                logger.error(f"[{service}] Request error: {e}")

            # If we got an exception (not 429), don't retry
            break

        self._log_usage(service, url, 0, 0, 0.0)
        return {
            "success": False,
            "data": None,
            "status_code": 0,
            "error": last_error or "Unknown error",
            "rate_limited": False,
            "retry_after": 0,
        }

    def _parse_rate_headers(self, service: str, headers):
        """Parse rate limit headers from API responses."""
        remaining = headers.get("X-RateLimit-Remaining") or headers.get("x-ratelimit-remaining")
        reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")

        if remaining is not None:
            try:
                info = {"remaining": int(remaining)}
                if reset:
                    info["reset_at"] = float(reset)
                with self._lock:
                    self._rate_limit_headers[service] = info
            except (ValueError, TypeError):
                pass

    def _log_usage(self, service: str, endpoint: str, status_code: int,
                   tokens: int, cost: float, campaign_id: int = None):
        """Log API call to api_usage_log table."""
        try:
            with self.db_manager.session_scope() as session:
                log = ApiUsageLog(
                    service=service,
                    endpoint=endpoint[:255],
                    tokens_used=tokens,
                    cost_usd=cost,
                    response_code=status_code,
                    campaign_id=campaign_id,
                )
                session.add(log)
        except Exception as e:
            logger.error(f"Failed to log API usage: {e}")

    def get_service_status(self, service: str) -> dict:
        """Get current status for a service."""
        with self._lock:
            self._prune_timestamps(service)
            limits = SERVICE_LIMITS.get(service, {})
            per_min_limit = limits.get("per_minute", 999)
            per_hour_limit = limits.get("per_hour", 9999)
            calls_min = self._count_calls(service, 60)
            calls_hour = self._count_calls(service, 3600)
            backoff = self._backoff_until.get(service, 0)

            return {
                "available": time.time() >= backoff and calls_min < per_min_limit,
                "remaining_this_minute": max(0, per_min_limit - calls_min),
                "remaining_this_hour": max(0, per_hour_limit - calls_hour),
                "backoff_until": datetime.fromtimestamp(backoff) if backoff > time.time() else None,
                "calls_today": self._count_calls(service, 86400),
            }

    def get_daily_cost(self, service: str = None) -> float:
        """Get total cost today for a service (or all services)."""
        try:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            with self.db_manager.session_scope() as session:
                from sqlalchemy import func
                query = session.query(func.sum(ApiUsageLog.cost_usd)).filter(
                    ApiUsageLog.timestamp >= today_start
                )
                if service:
                    query = query.filter(ApiUsageLog.service == service)
                result = query.scalar()
                return float(result) if result else 0.0
        except Exception:
            return 0.0
