"""
Aura — Chat Controller
Handles AI chat interactions in a background thread via the Orchestrator Engine.
"""

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from core.orchestrator_engine import OrchestratorEngine
from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("chat_controller")


class ChatController(QObject):
    """Controls the natural language chat interactions."""

    # Signals for UI connection
    response_ready = Signal(dict)       # Full intent + response dict
    thinking = Signal(bool)             # True when processing
    error = Signal(str)                 # Error message
    progress = Signal(int, str)         # percent, status text

    def __init__(
        self,
        db_manager: DatabaseManager,
        orchestrator: OrchestratorEngine,
        engines: dict,          # Dict of all engine instances
        parent=None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.orchestrator = orchestrator
        self.engines = engines
        self.command_history = None  # Injected from main_window
        self._worker = None

    def send_message(self, message: str, context: dict = None):
        """
        Process a user message through the orchestrator.
        Runs AI call in a background thread.
        """
        self.thinking.emit(True)

        def _work():
            root_cmd_id = None
            try:
                # Log inbound chat command
                if self.command_history:
                    try:
                        cmd_entry = self.command_history.log_user_command(
                            source="chat", text=message,
                        )
                        root_cmd_id = cmd_entry.get("data", {}).get("id") if cmd_entry.get("success") else None
                    except Exception:
                        pass

                # Parse the user's intent
                intent_dict = self.orchestrator.parse_intent(message, context)

                # If clarification needed, return without executing
                if intent_dict.get("clarification_needed"):
                    self._update_history(root_cmd_id, "completed", intent_dict)
                    return intent_dict

                # If confidence is high enough, execute the intent
                if intent_dict.get("confidence", 0) >= 0.5:
                    result = self.orchestrator.execute_intent(
                        intent_dict, self.engines
                    )
                    intent_dict["execution_result"] = result
                else:
                    intent_dict["execution_result"] = {
                        "success": True,
                        "data": {
                            "answer": intent_dict.get(
                                "response_text",
                                "I'm not sure I understood. Could you rephrase?"
                            )
                        },
                    }

                self._update_history(root_cmd_id, "completed", intent_dict)
                return intent_dict

            except Exception as e:
                logger.error(f"Chat processing error: {e}")
                self._update_history(root_cmd_id, "failed", {"error": str(e)})
                raise

        def _on_done(result):
            self.thinking.emit(False)
            if result:
                self.response_ready.emit(result)

        def _on_error(error):
            self.thinking.emit(False)
            self.error.emit(str(error))
            logger.error(f"Chat error: {error}")

        self._worker = ThreadWorker(_work)
        self._worker.finished.connect(_on_done)
        self._worker.error.connect(_on_error)
        self._worker.start()

    def confirm_action(self, intent_dict: dict):
        """
        Execute a previously confirmed intent (e.g., send emails).
        Called after user clicks "Confirm" on a confirmation card.
        """
        self.thinking.emit(True)

        def _work():
            root_cmd_id = None
            try:
                # Log the confirmed action execution
                if self.command_history:
                    try:
                        intent = intent_dict.get("intent", "confirmed_action")
                        cmd_entry = self.command_history.log_command(
                            source="chat",
                            command_type="confirmed_action",
                            command_text=f"Confirmed: {intent}",
                            actor_type="user",
                            intent=intent,
                            parameters=intent_dict.get("parameters"),
                            status="pending",
                        )
                        root_cmd_id = cmd_entry.get("data", {}).get("id") if cmd_entry.get("success") else None
                    except Exception:
                        pass

                result = self.orchestrator.execute_intent(
                    intent_dict, self.engines
                )
                intent_dict["execution_result"] = result

                self._update_history(root_cmd_id, "completed", intent_dict)
                return intent_dict
            except Exception as e:
                logger.error(f"Confirmation action error: {e}")
                self._update_history(root_cmd_id, "failed", {"error": str(e)})
                raise

        def _on_done(result):
            self.thinking.emit(False)
            if result:
                self.response_ready.emit(result)

        def _on_error(error):
            self.thinking.emit(False)
            self.error.emit(str(error))

        self._worker = ThreadWorker(_work)
        self._worker.finished.connect(_on_done)
        self._worker.error.connect(_on_error)
        self._worker.start()

    def get_history(self) -> list:
        """Return conversation history for display."""
        return self.orchestrator.get_history()

    def clear_history(self):
        """Clear conversation history."""
        self.orchestrator.clear_history()

    def _update_history(self, cmd_id, status, result_dict):
        """Update command history entry if available."""
        if not self.command_history or not cmd_id:
            return
        try:
            intent = result_dict.get("intent", "")
            response = result_dict.get("response_text", "")[:500]
            confidence = result_dict.get("confidence", 0)
            self.command_history.update_command_status(
                cmd_id, status,
                result={"intent": intent, "response": response, "confidence": confidence},
            )
        except Exception:
            pass

    # Aliases used by main_window wiring
    def process_message(self, message: str, context: dict = None):
        """Alias for send_message (used by main_window signal wiring)."""
        self.send_message(message, context)

    def execute_confirmed_action(self, intent_dict: dict):
        """Alias for confirm_action (used by main_window signal wiring)."""
        self.confirm_action(intent_dict)
