"""
Tests for Advanced Chat Panel features:
- ThinkingWidget (fun rotating phrases)
- StreamingBubble (word-by-word text reveal)
- ChatInput (multiline, Enter/Shift+Enter)
- FileAttachmentChip / FileDownloadCard
- ChatPanel stop generation, file handling
- ChatController stop_generation + send_message_with_files
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from ui.components.chat_panel import (
    ChatPanel, ThinkingWidget, StreamingBubble, ChatInput,
    MessageBubble, FileAttachmentChip, FileDownloadCard, ActionChip,
    THINKING_PHRASES, STREAM_WORD_DELAY_MS,
)
from controllers.chat_controller import ChatController, _MAX_FILE_CONTEXT_CHARS


# ─── ThinkingWidget Tests ──────────────────────────────────────────


class TestThinkingWidget:

    def test_thinking_widget_creates(self, qapp):
        w = ThinkingWidget()
        assert w.objectName() == "thinkingWidget"

    def test_thinking_widget_has_spinner(self, qapp):
        w = ThinkingWidget()
        assert w._spinner_label is not None
        assert w._spinner_label.text() in ["◐", "◓", "◑", "◒"]

    def test_thinking_widget_has_phrase_label(self, qapp):
        w = ThinkingWidget()
        assert w._phrase_label is not None

    def test_next_phrase_sets_text(self, qapp):
        w = ThinkingWidget()
        w._next_phrase()
        assert w._phrase_label.text() in THINKING_PHRASES

    def test_next_phrase_avoids_repeats(self, qapp):
        w = ThinkingWidget()
        seen = set()
        for _ in range(10):
            w._next_phrase()
            seen.add(w._phrase_label.text())
        # Should have gotten multiple different phrases
        assert len(seen) >= 5

    def test_spin_cycles_characters(self, qapp):
        w = ThinkingWidget()
        chars_seen = set()
        for _ in range(8):
            w._spin()
            chars_seen.add(w._spinner_label.text())
        assert len(chars_seen) == 4  # ◐ ◓ ◑ ◒

    def test_phrases_list_not_empty(self, qapp):
        assert len(THINKING_PHRASES) >= 20


# ─── StreamingBubble Tests ─────────────────────────────────────────


class TestStreamingBubble:

    def test_creates_with_correct_name(self, qapp):
        bubble = StreamingBubble("Hello world")
        assert bubble.objectName() == "chatBubbleAI"

    def test_starts_empty(self, qapp):
        bubble = StreamingBubble("Hello world")
        assert bubble._label.text() == ""

    def test_stop_streaming_reveals_all(self, qapp):
        text = "Hello world this is a test"
        bubble = StreamingBubble(text)
        bubble.start_streaming()
        bubble.stop_streaming()
        assert bubble._label.text() == text

    def test_reveal_next_adds_words(self, qapp):
        bubble = StreamingBubble("one two three")
        bubble._reveal_next()
        assert bubble._label.text() == "one"
        bubble._reveal_next()
        assert bubble._label.text() == "one two"
        bubble._reveal_next()
        assert bubble._label.text() == "one two three"

    def test_empty_text_immediate_finish(self, qapp):
        finished = []
        bubble = StreamingBubble("")
        bubble.stream_finished.connect(lambda: finished.append(True))
        bubble.start_streaming()
        assert len(finished) == 1

    def test_stream_delay_constant(self, qapp):
        assert STREAM_WORD_DELAY_MS > 0
        assert STREAM_WORD_DELAY_MS <= 100  # Should be snappy


# ─── ChatInput Tests ──────────────────────────────────────────────


class TestChatInput:

    def test_creates_with_correct_name(self, qapp):
        inp = ChatInput()
        assert inp.objectName() == "chatInput"

    def test_placeholder_text(self, qapp):
        inp = ChatInput()
        assert "Aura" in inp.placeholderText()

    def test_does_not_accept_rich_text(self, qapp):
        inp = ChatInput()
        assert inp.acceptRichText() is False

    def test_submit_signal_on_enter(self, qapp):
        inp = ChatInput()
        submitted = []
        inp.submit.connect(lambda: submitted.append(True))
        # Simulate Enter key
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        inp.keyPressEvent(event)
        assert len(submitted) == 1

    def test_no_submit_on_shift_enter(self, qapp):
        inp = ChatInput()
        submitted = []
        inp.submit.connect(lambda: submitted.append(True))
        # Simulate Shift+Enter
        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        inp.keyPressEvent(event)
        assert len(submitted) == 0


# ─── FileAttachmentChip Tests ─────────────────────────────────────


class TestFileAttachmentChip:

    def test_creates(self, qapp):
        chip = FileAttachmentChip("/path/to/file.txt")
        assert chip.objectName() == "fileChip"
        assert chip.file_path == "/path/to/file.txt"

    def test_long_name_truncated(self, qapp):
        long_name = "a" * 50 + ".csv"
        chip = FileAttachmentChip(f"/path/{long_name}")
        # Should not crash
        assert chip.file_path.endswith(".csv")

    def test_removed_signal(self, qapp):
        chip = FileAttachmentChip("/path/to/test.txt")
        removed_paths = []
        chip.removed.connect(lambda p: removed_paths.append(p))
        # Simulate remove button click
        chip.removed.emit("/path/to/test.txt")
        assert removed_paths == ["/path/to/test.txt"]


# ─── FileDownloadCard Tests ───────────────────────────────────────


class TestFileDownloadCard:

    def test_creates(self, qapp):
        card = FileDownloadCard("report.csv", "col1,col2\na,b")
        assert card.objectName() == "fileDownloadCard"

    def test_save_file(self, qapp):
        content = "hello,world\n1,2"
        card = FileDownloadCard("test.csv", content)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            tmppath = f.name

        try:
            with patch.object(
                type(card), "_save_file",
                lambda self: None
            ):
                # Just verify save_file method exists
                assert hasattr(card, "_save_file")
        finally:
            os.unlink(tmppath)


# ─── ChatPanel Tests ──────────────────────────────────────────────


class TestChatPanel:

    def test_creates(self, qapp):
        panel = ChatPanel()
        assert panel.objectName() == "chatPanel"

    def test_starts_hidden(self, qapp):
        panel = ChatPanel()
        assert panel._is_visible is False

    def test_toggle(self, qapp):
        panel = ChatPanel()
        panel.toggle()
        assert panel._is_visible is True
        panel.toggle()
        assert panel._is_visible is False

    def test_add_message_user(self, qapp):
        panel = ChatPanel()
        panel.add_message("Hello", is_user=True)
        # Should have added a bubble (count includes stretch + new bubble)
        assert panel.messages_layout.count() >= 2

    def test_add_message_ai(self, qapp):
        panel = ChatPanel()
        panel.add_message("Response", is_user=False)
        assert panel.messages_layout.count() >= 2

    def test_add_streaming_message(self, qapp):
        panel = ChatPanel()
        panel.add_streaming_message("Hello world test")
        assert panel._current_streaming_bubble is not None

    def test_streaming_bubble_finishes(self, qapp):
        panel = ChatPanel()
        panel.add_streaming_message("Hello world")
        # Force stop to complete
        panel._current_streaming_bubble.stop_streaming()
        assert panel._current_streaming_bubble is None

    def test_show_thinking_shows_widget(self, qapp):
        panel = ChatPanel()
        panel.show_thinking(True)
        assert panel._is_thinking is True
        # Widget is not hidden (but parent panel may not be shown)
        assert not panel.thinking_widget.isHidden()

    def test_show_thinking_hides_widget(self, qapp):
        panel = ChatPanel()
        panel.show_thinking(True)
        panel.show_thinking(False)
        assert panel._is_thinking is False

    def test_stop_button_swaps(self, qapp):
        panel = ChatPanel()
        panel.show_thinking(True)
        assert panel._send_btn.objectName() == "chatStopButton"
        panel.show_thinking(False)
        assert panel._send_btn.objectName() == "chatSendButton"

    def test_add_file_download(self, qapp):
        panel = ChatPanel()
        initial_count = panel.messages_layout.count()
        panel.add_file_download("report.csv", "data,here")
        assert panel.messages_layout.count() == initial_count + 1

    def test_file_attachment(self, qapp):
        panel = ChatPanel()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test")
            tmppath = f.name
        try:
            panel._add_attachment(tmppath)
            assert tmppath in panel._attached_files
            assert not panel._file_bar.isHidden()

            # Remove it
            panel._remove_attachment(tmppath)
            assert tmppath not in panel._attached_files
        finally:
            os.unlink(tmppath)

    def test_duplicate_attachment_ignored(self, qapp):
        panel = ChatPanel()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            tmppath = f.name
        try:
            panel._add_attachment(tmppath)
            panel._add_attachment(tmppath)
            assert panel._attached_files.count(tmppath) == 1
        finally:
            os.unlink(tmppath)

    def test_clear_attachments(self, qapp):
        panel = ChatPanel()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            tmppath = f.name
        try:
            panel._add_attachment(tmppath)
            panel._clear_attachments()
            assert len(panel._attached_files) == 0
            assert not panel._file_bar.isVisible()
        finally:
            os.unlink(tmppath)

    def test_on_send_emits_signal(self, qapp):
        panel = ChatPanel()
        messages = []
        panel.message_sent.connect(lambda m: messages.append(m))
        panel.input_field.setPlainText("Hello")
        panel._on_send()
        assert messages == ["Hello"]

    def test_on_send_with_files_emits(self, qapp):
        panel = ChatPanel()
        results = []
        panel.message_sent_with_files.connect(
            lambda m, f: results.append((m, f))
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            tmppath = f.name
        try:
            panel._add_attachment(tmppath)
            panel.input_field.setPlainText("Check this file")
            panel._on_send()
            assert len(results) == 1
            assert results[0][0] == "Check this file"
            assert tmppath in results[0][1]
        finally:
            os.unlink(tmppath)

    def test_on_stop_emits_signal(self, qapp):
        panel = ChatPanel()
        stopped = []
        panel.stop_requested.connect(lambda: stopped.append(True))
        panel._is_thinking = True
        panel._on_stop()
        assert len(stopped) == 1

    def test_handle_response_streaming(self, qapp):
        panel = ChatPanel()
        response = {
            "intent": "chat",
            "response_text": "Here is the answer",
            "execution_result": {"success": True, "data": {}},
        }
        panel.handle_response(response)
        # Should have created a streaming bubble
        assert panel.messages_layout.count() >= 2

    def test_handle_response_with_file(self, qapp):
        panel = ChatPanel()
        response = {
            "intent": "export_data",
            "response_text": "Here's your file",
            "execution_result": {
                "success": True,
                "data": {
                    "_file_name": "export.csv",
                    "_file_content": "a,b\n1,2",
                },
            },
        }
        initial = panel.messages_layout.count()
        panel.handle_response(response)
        # Should have file card + streaming message
        assert panel.messages_layout.count() >= initial + 2

    def test_show_typing_alias(self, qapp):
        panel = ChatPanel()
        panel.show_typing(True)
        assert panel._is_thinking is True
        panel.show_typing(False)
        assert panel._is_thinking is False

    def test_handle_list_leads_response(self, qapp):
        panel = ChatPanel()
        response = {
            "intent": "list_leads",
            "response_text": "Here are your 3 leads:",
            "execution_result": {
                "success": True,
                "data": {
                    "leads": [
                        {"num": 1, "business_name": "Acme", "email": "a@b.com", "status": "new"},
                        {"num": 2, "business_name": "Beta", "email": "b@c.com", "status": "new"},
                    ],
                    "total": 2,
                    "_text_summary": "1. **Acme** (new) — a@b.com\n2. **Beta** (new) — b@c.com",
                },
            },
        }
        initial = panel.messages_layout.count()
        panel.handle_response(response)
        assert panel.messages_layout.count() > initial

    def test_handle_list_leads_empty(self, qapp):
        panel = ChatPanel()
        response = {
            "intent": "list_leads",
            "response_text": "",
            "execution_result": {
                "success": True,
                "data": {"leads": [], "total": 0},
            },
        }
        initial = panel.messages_layout.count()
        panel.handle_response(response)
        assert panel.messages_layout.count() > initial

    def test_handle_show_lead_detail(self, qapp):
        panel = ChatPanel()
        response = {
            "intent": "show_lead_detail",
            "response_text": "Here are the details:",
            "execution_result": {
                "success": True,
                "data": {
                    "id": 1,
                    "business_name": "Acme Corp",
                    "email": "info@acme.com",
                    "status": "qualified",
                    "city": "Austin",
                },
            },
        }
        initial = panel.messages_layout.count()
        panel.handle_response(response)
        # Should have streaming message + action block
        assert panel.messages_layout.count() >= initial + 2


# ─── Orchestrator list_leads Tests ────────────────────────────────


class TestOrchestratorListLeads:

    def test_list_leads_all(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        from database.schema import Campaign, Lead

        # Seed some leads
        with db.session_scope() as session:
            camp = Campaign(name="Test Campaign", status="active")
            session.add(camp)
            session.flush()
            for i in range(5):
                session.add(Lead(
                    campaign_id=camp.id,
                    business_name=f"Business {i}",
                    email=f"lead{i}@test.com",
                    city="Austin",
                    status="new",
                ))

        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_list_leads({}, {})
        assert result["success"] is True
        assert len(result["data"]["leads"]) == 5
        assert result["data"]["total"] == 5
        assert "_text_summary" in result["data"]

    def test_list_leads_by_campaign(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        from database.schema import Campaign, Lead

        with db.session_scope() as session:
            camp = Campaign(name="Alpha Campaign", status="active")
            session.add(camp)
            session.flush()
            session.add(Lead(
                campaign_id=camp.id, business_name="Alpha Lead",
                email="a@test.com", status="new",
            ))

        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_list_leads({"campaign_name": "Alpha"}, {})
        assert result["success"] is True
        assert len(result["data"]["leads"]) >= 1

    def test_list_leads_campaign_not_found(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_list_leads({"campaign_name": "NonExistent999"}, {})
        assert result["success"] is False

    def test_list_leads_empty(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_list_leads({"status": "nonexistent_status_xyz"}, {})
        assert result["success"] is True
        assert result["data"]["total"] == 0

    def test_show_lead_detail_by_id(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        from database.schema import Campaign, Lead

        with db.session_scope() as session:
            camp = Campaign(name="Detail Test", status="active")
            session.add(camp)
            session.flush()
            lead = Lead(
                campaign_id=camp.id, business_name="Detail Biz",
                email="detail@test.com", city="Dallas", status="qualified",
            )
            session.add(lead)
            session.flush()
            lead_id = lead.id

        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_show_lead_detail({"lead_id": lead_id}, {})
        assert result["success"] is True
        assert result["data"]["business_name"] == "Detail Biz"
        assert result["data"]["city"] == "Dallas"

    def test_show_lead_detail_by_name(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        from database.schema import Campaign, Lead

        with db.session_scope() as session:
            camp = Campaign(name="Name Test", status="active")
            session.add(camp)
            session.flush()
            session.add(Lead(
                campaign_id=camp.id, business_name="Unique Name Corp",
                email="unique@test.com", status="new",
            ))

        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_show_lead_detail({"business_name": "Unique Name"}, {})
        assert result["success"] is True
        assert "Unique Name Corp" in result["data"]["business_name"]

    def test_show_lead_detail_not_found(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_show_lead_detail({"lead_id": 99999}, {})
        assert result["success"] is False

    def test_show_lead_detail_no_params(self, qapp, db):
        from core.orchestrator_engine import OrchestratorEngine
        orch = OrchestratorEngine(db, MagicMock())
        result = orch._exec_show_lead_detail({}, {})
        assert result["success"] is False


# ─── ChatController Tests ─────────────────────────────────────────


class TestChatControllerAdvanced:

    def _make_controller(self, db):
        orchestrator = MagicMock()
        orchestrator.parse_intent.return_value = {
            "intent": "chat",
            "confidence": 0.9,
            "response_text": "test response",
        }
        orchestrator.execute_intent.return_value = {
            "success": True,
            "data": {"answer": "done"},
        }
        return ChatController(db, orchestrator, {})

    def test_stop_generation(self, qapp, db):
        ctrl = self._make_controller(db)
        # No worker yet — shouldn't crash
        ctrl.stop_generation()

    def test_stop_generation_cancels_worker(self, qapp, db):
        ctrl = self._make_controller(db)
        mock_worker = MagicMock()
        ctrl._worker = mock_worker
        ctrl.stop_generation()
        mock_worker.cancel.assert_called_once()

    def test_send_message_with_files(self, qapp, db):
        ctrl = self._make_controller(db)
        # Create a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as f:
            f.write("test content here")
            tmppath = f.name

        try:
            sent = []
            ctrl.thinking.connect(lambda t: sent.append(t))
            ctrl.send_message_with_files("Analyze this", [tmppath])
            # Should have started thinking
            assert True in sent
        finally:
            os.unlink(tmppath)

    def test_send_message_with_large_file(self, qapp, db):
        ctrl = self._make_controller(db)
        # Create a very large file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as f:
            f.write("x" * (_MAX_FILE_CONTEXT_CHARS * 3))
            tmppath = f.name

        try:
            # Should not crash even with large file
            ctrl.send_message_with_files("Analyze", [tmppath])
        finally:
            os.unlink(tmppath)

    def test_send_message_with_missing_file(self, qapp, db):
        ctrl = self._make_controller(db)
        # Non-existent file should not crash
        ctrl.send_message_with_files("Check", ["/nonexistent/file.txt"])

    def test_send_message_with_empty_files(self, qapp, db):
        ctrl = self._make_controller(db)
        # Empty file list should just send message normally
        sent_msgs = []
        ctrl.thinking.connect(lambda t: sent_msgs.append(t))
        ctrl.send_message_with_files("Hello", [])
        assert True in sent_msgs

    def test_process_message_alias(self, qapp, db):
        ctrl = self._make_controller(db)
        sent = []
        ctrl.thinking.connect(lambda t: sent.append(t))
        ctrl.process_message("test")
        assert True in sent
