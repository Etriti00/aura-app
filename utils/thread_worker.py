"""
Aura — Thread Worker
Reusable QThread wrapper with result, error, progress, and finished signals.
Used by all controllers for background operations.
"""

from PySide6.QtCore import QThread, Signal, QObject
import inspect
import traceback


class WorkerSignals(QObject):
    """Signals available from a running worker thread."""
    result = Signal(object)     # Return value of the function
    error = Signal(str)         # Error message if function raises
    progress = Signal(int)      # 0–100 progress updates
    finished = Signal()         # Always emitted at the end


class ThreadWorker(QThread):
    """
    Generic background worker that runs any callable in a QThread.

    Usage:
        worker = ThreadWorker(fn=my_function, kwargs={"arg1": val1})
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.progress.connect(on_progress)
        worker.signals.finished.connect(on_finished)
        worker.start()
    """

    def __init__(self, fn, args=None, kwargs=None):
        super().__init__()
        self.fn = fn
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def run(self):
        """Execute the function and emit appropriate signals."""
        try:
            # Only inject callbacks if the function can accept them
            sig = inspect.signature(self.fn)
            params = sig.parameters
            accepts_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
            if accepts_kwargs or "_progress_callback" in params:
                self.kwargs["_progress_callback"] = self.signals.progress.emit
            if accepts_kwargs or "_cancel_checker" in params:
                self.kwargs["_cancel_checker"] = lambda: self._is_cancelled

            result = self.fn(*self.args, **self.kwargs)
            if not self._is_cancelled:
                self.signals.result.emit(result)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)
        finally:
            self.signals.finished.emit()

    def cancel(self):
        """Request cancellation of the running task."""
        self._is_cancelled = True
