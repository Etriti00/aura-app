"""
Aura — Research Controller
Signal-based UI controller for the Lead Research Engine.
"""

from PySide6.QtCore import QObject, Signal

from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("research_controller")


class ResearchController(QObject):
    """Bridges the ResearchEngine to the Research UI page via signals."""

    research_started = Signal(int)           # lead_id
    research_completed = Signal(int, dict)   # lead_id, report_data
    research_failed = Signal(int, str)       # lead_id, error
    queue_updated = Signal(list)             # list of queue items
    reports_ready = Signal(list)             # list of report summaries
    report_detail_ready = Signal(dict)       # full report data
    provider_status_ready = Signal(dict)     # provider availability

    def __init__(self, research_engine, parent=None):
        super().__init__(parent)
        self.engine = research_engine
        self._workers = []  # prevent GC of running QThreads

    def _track_worker(self, worker):
        """Store worker reference and clean up finished workers."""
        self._workers = [w for w in self._workers if w.isRunning()]
        self._workers.append(worker)

    def research_lead(self, lead_id: int, depth: str = "auto"):
        """Start research for a lead in a background thread."""
        self.research_started.emit(lead_id)

        def _work(**kwargs):
            return self.engine.research_lead(lead_id, depth=depth)

        def _done(result):
            if result.get("success"):
                self.research_completed.emit(lead_id, result.get("data", {}))
            else:
                self.research_failed.emit(lead_id, result.get("error", "Unknown error"))
            self.refresh_queue()

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def refresh_queue(self):
        """Refresh the research queue."""
        def _work(**kwargs):
            return self.engine.get_research_queue()

        def _done(result):
            self.queue_updated.emit(result.get("data", []))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def load_reports(self, campaign_id: int = None, limit: int = 50):
        """Load all research reports."""
        def _work(**kwargs):
            return self.engine.get_all_reports(campaign_id=campaign_id, limit=limit)

        def _done(result):
            self.reports_ready.emit(result.get("data", []))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def load_report_detail(self, lead_id: int):
        """Load a full research report for a lead."""
        def _work(**kwargs):
            return self.engine.get_report(lead_id)

        def _done(result):
            if result.get("success"):
                self.report_detail_ready.emit(result.get("data", {}))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def check_providers(self):
        """Check which research providers are available."""
        status = self.engine.get_provider_status()
        self.provider_status_ready.emit(status)
