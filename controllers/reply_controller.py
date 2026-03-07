"""
Aura — Reply Controller
Runs a 2-hr QTimer loop to check IMAP inbox for replies.
"""

from PySide6.QtCore import QObject, Signal, QTimer

from database.db_manager import DatabaseManager
from core.reply_detector import ReplyDetector
from config import REPLY_CHECK_INTERVAL_MS
from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("reply_controller")


class ReplyController(QObject):
    """Background controller that polls IMAP for reply detection."""

    reply_detected = Signal(int, str)          # lead_id, business_name
    batch_complete = Signal(int)               # total_replies_found
    check_error = Signal(str)                  # error_message
    triage_complete = Signal(dict)             # triage result dict

    def __init__(
        self,
        db_manager: DatabaseManager,
        reply_detector: ReplyDetector,
        parent=None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.detector = reply_detector
        self.triage_engine = None
        self._worker = None
        self._triage_worker = None

        # 2-hour timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_for_replies)
        self._timer.setInterval(REPLY_CHECK_INTERVAL_MS)

        # Daily triage timer (defaults to 8 AM, configurable)
        self._triage_timer = QTimer(self)
        self._triage_timer.timeout.connect(self._check_triage_schedule)
        self._triage_timer.setInterval(60_000)  # Check every minute
        self._triage_hour = 8  # Default 8 AM
        self._last_triage_date = None

    def start(self):
        """Start the background reply check timer."""
        logger.info("Reply controller started (2-hr interval)")
        self._timer.start()
        self._triage_timer.start()

    def stop(self):
        """Stop the reply check timer."""
        self._timer.stop()
        self._triage_timer.stop()

    def check_now(self):
        """Manually trigger a reply check."""
        self.check_for_replies()

    def check_for_replies(self):
        """Poll IMAP inbox for replies."""
        logger.info("Checking inbox for replies…")

        def _work():
            try:
                replies = self.detector.check_inbox()

                if not replies:
                    return []

                processed = []
                for reply in replies:
                    result = self.detector.mark_lead_replied(
                        lead_id=reply["lead_id"],
                        reply_body=reply["reply_body"],
                        received_at=reply["received_at"],
                    )
                    if result.get("success"):
                        if not result.get("data", {}).get("already_replied"):
                            processed.append(reply)
                            logger.info(f"Reply detected from lead {reply['lead_id']}")

                return processed

            except Exception as e:
                logger.error(f"Reply check error: {e}")
                raise

        def _on_done(result):
            if result:
                for reply in result:
                    # Get business name for the signal
                    from database.schema import Lead
                    with self.db_manager.session_scope() as session:
                        lead = session.query(Lead).filter_by(id=reply["lead_id"]).first()
                        name = lead.business_name if lead else f"Lead #{reply['lead_id']}"
                    self.reply_detected.emit(reply["lead_id"], name)

                self.batch_complete.emit(len(result))
                logger.info(f"Reply check complete: {len(result)} new replies")

        def _on_error(error):
            self.check_error.emit(str(error))
            logger.error(f"Reply check failed: {error}")

        self._worker = ThreadWorker(_work)
        self._worker.finished.connect(_on_done)
        self._worker.error.connect(_on_error)
        self._worker.start()

    # ─── Triage scheduling ────────────────────────────────────

    def set_triage_hour(self, hour: int):
        """Set the hour (0-23) for daily triage."""
        self._triage_hour = max(0, min(23, hour))

    def _check_triage_schedule(self):
        """Check if it's time to run the daily triage."""
        from datetime import datetime, date
        now = datetime.now()
        today = date.today()

        if (
            self.triage_engine
            and now.hour == self._triage_hour
            and self._last_triage_date != today
        ):
            self._last_triage_date = today
            self.run_triage()

    def run_triage(self):
        """Run the inbox triage in a background thread."""
        if not self.triage_engine:
            logger.warning("Triage engine not set — skipping triage")
            return

        logger.info("Running inbox triage...")

        def _work():
            return self.triage_engine.run_morning_triage()

        def _on_done(result):
            logger.info(f"Triage done: {result.get('total_emails', 0)} emails")
            self.triage_complete.emit(result)

        def _on_error(error):
            logger.error(f"Triage failed: {error}")
            self.check_error.emit(f"Triage error: {error}")

        self._triage_worker = ThreadWorker(_work)
        self._triage_worker.finished.connect(_on_done)
        self._triage_worker.error.connect(_on_error)
        self._triage_worker.start()
