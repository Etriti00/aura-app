"""
Aura — Chat Controller
Handles AI chat interactions in a background thread via the Orchestrator Engine.
Supports stop generation, file attachments, and file delivery.
"""

import os

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from core.orchestrator_engine import OrchestratorEngine
from utils.logger import get_logger
from utils.thread_worker import ThreadWorker

logger = get_logger("chat_controller")

# Max size for file content included in AI context (chars)
_MAX_FILE_CONTEXT_CHARS = 8000


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
        self.correction_memory = None  # Injected from main_window
        self._worker = None
        self._last_response_text = ""

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

                # Detect corrections and store rules
                if self.correction_memory:
                    try:
                        if self.correction_memory.looks_like_correction(message):
                            self.correction_memory.extract_and_store(
                                message, self._last_response_text,
                            )
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
                self._last_response_text = result.get("response_text", "")
                self.response_ready.emit(result)

        def _on_error(error):
            self.thinking.emit(False)
            self.error.emit(str(error))
            logger.error(f"Chat error: {error}")

        self._worker = ThreadWorker(_work)
        self._worker.signals.result.connect(_on_done)
        self._worker.signals.error.connect(_on_error)
        self._worker.start()

    def send_message_with_files(self, message: str, file_paths: list):
        """
        Process a message with attached files.
        Reads file contents and includes them in the AI context.
        """
        # Build file context string
        file_context_parts = []
        for path in file_paths:
            try:
                name = os.path.basename(path)
                size = os.path.getsize(path)
                if size > _MAX_FILE_CONTEXT_CHARS * 2:
                    file_context_parts.append(
                        f"[File: {name} — {size:,} bytes, too large to include inline]"
                    )
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(_MAX_FILE_CONTEXT_CHARS)
                if len(content) >= _MAX_FILE_CONTEXT_CHARS:
                    content = content[:_MAX_FILE_CONTEXT_CHARS] + "\n… (truncated)"
                file_context_parts.append(
                    f"--- File: {name} ---\n{content}\n--- End of {name} ---"
                )
            except Exception as e:
                file_context_parts.append(f"[File: {os.path.basename(path)} — error reading: {e}]")

        if file_context_parts:
            augmented_message = (
                message + "\n\n[Attached files]\n" + "\n\n".join(file_context_parts)
            )
        else:
            augmented_message = message

        context = {"attached_files": [os.path.basename(p) for p in file_paths]}
        self.send_message(augmented_message, context)

    def stop_generation(self):
        """Cancel the current background worker."""
        if self._worker:
            self._worker.cancel()
            logger.info("Chat generation cancelled by user")

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
        self._worker.signals.result.connect(_on_done)
        self._worker.signals.error.connect(_on_error)
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
