"""
Aura — Voice Controller
Signal-based UI controller for the Voice Call Engine.
"""

from PySide6.QtCore import QObject, Signal

from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("voice_controller")


class VoiceController(QObject):
    """Bridges the VoiceCallEngine to the Calls UI page via signals."""

    call_started = Signal(int, dict)           # call_id, call_data
    call_ended = Signal(int, dict)             # call_id, result_data
    call_transcript_update = Signal(int, str, str)  # call_id, speaker, text
    call_failed = Signal(int, str)             # call_id, error
    server_status = Signal(bool)               # ws_server running
    call_history_ready = Signal(list)          # list of call records
    call_detail_ready = Signal(dict)           # full call transcript
    active_calls_ready = Signal(list)          # active call list
    provider_status_ready = Signal(dict)       # provider availability

    def __init__(self, voice_engine, parent=None):
        super().__init__(parent)
        self.engine = voice_engine
        self._workers = []  # prevent GC of running QThreads

    def _track_worker(self, worker):
        """Store worker reference and clean up finished workers."""
        self._workers = [w for w in self._workers if w.isRunning()]
        self._workers.append(worker)

    def initiate_call(self, lead_id: int, agent_id: int = None):
        """Start an outbound call in a background thread."""
        def _work(**kwargs):
            return self.engine.initiate_call(lead_id, agent_id=agent_id)

        def _done(result):
            if result.get("success"):
                data = result.get("data", {})
                self.call_started.emit(data.get("call_id", 0), data)
            else:
                self.call_failed.emit(0, result.get("error", "Unknown error"))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def end_call(self, call_id: int):
        """End an active call."""
        def _work(**kwargs):
            return self.engine.end_call(call_id)

        def _done(result):
            if result.get("success"):
                self.call_ended.emit(call_id, result.get("data", {}))
            else:
                self.call_failed.emit(call_id, result.get("error", "Unknown error"))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def load_call_history(self, lead_id: int = None, limit: int = 50):
        """Load call history."""
        def _work(**kwargs):
            return self.engine.get_call_history(lead_id=lead_id, limit=limit)

        def _done(result):
            self.call_history_ready.emit(result.get("data", []))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def load_call_detail(self, call_id: int):
        """Load a full call transcript."""
        def _work(**kwargs):
            return self.engine.get_call_transcript(call_id)

        def _done(result):
            if result.get("success"):
                self.call_detail_ready.emit(result.get("data", {}))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def load_active_calls(self):
        """Get currently active calls."""
        result = self.engine.get_active_calls()
        self.active_calls_ready.emit(result.get("data", []))

    def start_server(self):
        """Start the WS server."""
        def _work(**kwargs):
            return self.engine.start_server()

        def _done(result):
            self.server_status.emit(result.get("success", False))

        worker = ThreadWorker(_work)
        worker.signals.result.connect(_done)
        self._track_worker(worker)
        worker.start()

    def check_providers(self):
        """Check which voice providers are available."""
        status = self.engine.get_provider_status()
        self.provider_status_ready.emit(status)
