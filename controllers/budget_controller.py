"""
Aura — Budget Controller
Manages budget pacing lifecycle, periodic status updates,
tier-downgrade detection, and budget warning thresholds.
"""

from PySide6.QtCore import QObject, Signal, QTimer

from core.pacing_engine import PacingEngine
from config import PACING_CHECK_INTERVAL_MS
from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("budget_controller")


class BudgetController(QObject):
    """Controls the budget pacing lifecycle and emits status updates."""

    # Signals
    status_updated = Signal(dict)        # Pacing status dict every tick
    tier_downgraded = Signal(str, str)   # (from_tier, to_tier)
    budget_warning = Signal(str)         # Warning messages
    budget_expired = Signal()            # Time window or budget exhausted
    preflight_result = Signal(dict)      # Pre-flight check result

    def __init__(self, pacing_engine: PacingEngine, parent=None):
        super().__init__(parent)
        self.pacing_engine = pacing_engine

        self._timer = QTimer(self)
        self._timer.setInterval(PACING_CHECK_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        self._last_max_tier = "sonnet"
        self._notified_thresholds: set = set()
        self._worker = None

    # ─── Lifecycle ─────────────────────────────────────────────────

    def start_pacing(self, budget_usd: float, time_window_hours: float,
                     eco_mode: bool = True):
        """Activate pacing and start the monitoring timer."""
        result = self.pacing_engine.activate(budget_usd, time_window_hours, eco_mode)
        if result.get("success"):
            self._last_max_tier = "sonnet"
            self._notified_thresholds.clear()
            self._timer.start()
            # Emit initial status
            self._tick()
            logger.info("Budget pacing started")
        else:
            self.budget_warning.emit(result.get("error", "Failed to activate pacing"))

    def stop_pacing(self):
        """Deactivate pacing and stop the timer."""
        self._timer.stop()
        self.pacing_engine.deactivate()
        self._notified_thresholds.clear()
        self.status_updated.emit(self.pacing_engine.get_status())
        logger.info("Budget pacing stopped")

    def pause_pacing(self):
        """Pause pacing (timer keeps running for status but pacing is paused)."""
        self.pacing_engine.pause()

    def resume_pacing(self):
        """Resume paused pacing."""
        self.pacing_engine.resume()

    # ─── Pre-flight ────────────────────────────────────────────────

    def run_preflight(self, estimated_tasks: int, avg_tokens: int = 500):
        """Run pre-flight check in background thread."""
        def _work():
            return self.pacing_engine.pre_flight_check(estimated_tasks, avg_tokens)

        def _done(result):
            self.preflight_result.emit(result)

        def _error(err):
            self.preflight_result.emit({
                "feasible": False,
                "message": f"Pre-flight check error: {err}",
            })

        self._worker = ThreadWorker(_work)
        self._worker.signals.result.connect(_done)
        self._worker.signals.error.connect(_error)
        self._worker.start()

    # ─── Periodic monitoring ───────────────────────────────────────

    def _tick(self):
        """Called every PACING_CHECK_INTERVAL_MS by the timer."""
        try:
            status = self.pacing_engine.get_status()
            self.status_updated.emit(status)

            if not status.get("active"):
                if status.get("status") == "expired":
                    self._timer.stop()
                    self.budget_expired.emit()
                return

            # Check tier changes
            current_tier = status.get("current_max_tier", "sonnet")
            if current_tier != self._last_max_tier:
                old_tier = self._last_max_tier
                self._last_max_tier = current_tier
                self.tier_downgraded.emit(old_tier, current_tier)
                logger.info(f"Tier changed: {old_tier} → {current_tier}")

            # Check budget thresholds
            percent = status.get("percent_spent", 0.0)
            for threshold in [80, 90, 95]:
                if percent >= threshold and threshold not in self._notified_thresholds:
                    self._notified_thresholds.add(threshold)
                    remaining = status.get("remaining_usd", 0)
                    self.budget_warning.emit(
                        f"Budget {threshold}% spent — ${remaining:.2f} remaining"
                    )

            # Check if remaining_hours hit zero
            if status.get("remaining_hours", 0) <= 0:
                self._timer.stop()
                self.budget_expired.emit()

        except Exception as e:
            logger.error(f"Pacing tick error: {e}")

    # ─── Synchronous getter ────────────────────────────────────────

    def get_current_status(self) -> dict:
        """Get current pacing status synchronously."""
        return self.pacing_engine.get_status()
