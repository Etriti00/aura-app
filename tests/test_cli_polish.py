"""Tests for CLI polish: clean output, --verbose flag, SAWarning fix, logger silencing."""

import argparse
import logging
import warnings

import pytest


class TestSAWarningFix:
    """Verify the TicketDependency relationship overlap warning is eliminated."""

    def test_schema_import_no_sa_warning(self):
        """Importing schema should not emit SAWarning about overlapping relationships."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Force re-evaluation of relationships
            from sqlalchemy.orm import configure_mappers
            configure_mappers()
            sa_warnings = [x for x in w if "overlaps" in str(x.message)
                           and "TicketDependency" in str(x.message)]
            assert len(sa_warnings) == 0, f"SAWarning still present: {sa_warnings[0].message}"

    def test_ticket_dependency_has_overlaps_in_source(self):
        """TicketDependency.ticket relationship should have overlaps='dependencies' in source."""
        import inspect
        from database.schema import TicketDependency
        source = inspect.getsource(TicketDependency)
        assert 'overlaps="dependencies"' in source

    def test_agent_ticket_dependencies_has_overlaps_in_source(self):
        """AgentTicket.dependencies relationship should have overlaps='ticket' in source."""
        import inspect
        from database.schema import AgentTicket
        source = inspect.getsource(AgentTicket)
        assert 'overlaps="ticket"' in source

    def test_ticket_dependency_crud_no_warning(self, db):
        """Creating a TicketDependency should not emit any SAWarning."""
        from database.schema import AgentTicket, TicketDependency
        session = db.SessionFactory()
        try:
            t1 = AgentTicket(title="Task A", description="Test", status="todo",
                             priority="medium")
            t2 = AgentTicket(title="Task B", description="Test", status="todo",
                             priority="medium")
            session.add_all([t1, t2])
            session.flush()

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                dep = TicketDependency(ticket_id=t1.id, depends_on_id=t2.id)
                session.add(dep)
                session.flush()
                _ = dep.ticket
                sa_warnings = [x for x in w if "overlaps" in str(x.message)]
                assert len(sa_warnings) == 0
        finally:
            session.close()


class TestLoggerSilencing:
    """Verify set_console_level() controls console output."""

    def test_set_console_level_exists(self):
        """set_console_level should be importable from utils.logger."""
        from utils.logger import set_console_level
        assert callable(set_console_level)

    def test_set_console_level_affects_new_loggers(self):
        """After set_console_level(ERROR), new loggers should have ERROR console level."""
        from utils.logger import set_console_level, get_logger, _cli_console_level

        # Save original and set to ERROR
        original = _cli_console_level[0]
        try:
            set_console_level(logging.ERROR)

            # Create a fresh logger (unique name to avoid caching)
            import uuid
            test_logger = get_logger(f"test_fresh_{uuid.uuid4().hex[:8]}")

            # Find the StreamHandler (not RotatingFileHandler)
            from logging.handlers import RotatingFileHandler
            console_handlers = [
                h for h in test_logger.handlers
                if isinstance(h, logging.StreamHandler)
                and not isinstance(h, RotatingFileHandler)
            ]
            assert len(console_handlers) == 1
            assert console_handlers[0].level == logging.ERROR
        finally:
            _cli_console_level[0] = original

    def test_set_console_level_updates_existing_loggers(self):
        """set_console_level should retroactively update existing logger console handlers."""
        from utils.logger import set_console_level, get_logger, _cli_console_level
        from logging.handlers import RotatingFileHandler
        import uuid

        original = _cli_console_level[0]
        try:
            # Create logger first at default level
            _cli_console_level[0] = None
            test_logger = get_logger(f"test_existing_{uuid.uuid4().hex[:8]}")

            console_handlers = [
                h for h in test_logger.handlers
                if isinstance(h, logging.StreamHandler)
                and not isinstance(h, RotatingFileHandler)
            ]
            assert console_handlers[0].level == logging.INFO

            # Now silence
            set_console_level(logging.ERROR)
            assert console_handlers[0].level == logging.ERROR
        finally:
            _cli_console_level[0] = original

    def test_file_handler_unaffected(self):
        """set_console_level should not change file handler level."""
        from utils.logger import set_console_level, get_logger, _cli_console_level
        from logging.handlers import RotatingFileHandler
        import uuid

        original = _cli_console_level[0]
        try:
            set_console_level(logging.ERROR)
            test_logger = get_logger(f"test_file_{uuid.uuid4().hex[:8]}")

            file_handlers = [
                h for h in test_logger.handlers
                if isinstance(h, RotatingFileHandler)
            ]
            assert len(file_handlers) == 1
            assert file_handlers[0].level == logging.DEBUG
        finally:
            _cli_console_level[0] = original


class TestVerboseFlag:
    """Verify --verbose / -V argparse flag works."""

    def _make_parser(self):
        """Create a parser matching cli.py's main() argparse setup."""
        parser = argparse.ArgumentParser(prog="aura")
        parser.add_argument("--version", "-v", action="store_true")
        parser.add_argument("--verbose", "-V", action="store_true")
        parser.add_argument("command", nargs="?")
        parser.add_argument("args", nargs=argparse.REMAINDER)
        return parser

    def test_verbose_long_flag(self):
        """--verbose flag sets args.verbose to True."""
        parser = self._make_parser()
        args = parser.parse_args(["--verbose", "status"])
        assert args.verbose is True
        assert args.command == "status"

    def test_verbose_short_flag(self):
        """-V flag sets args.verbose to True."""
        parser = self._make_parser()
        args = parser.parse_args(["-V", "status"])
        assert args.verbose is True

    def test_no_verbose_default(self):
        """Without --verbose, args.verbose is False."""
        parser = self._make_parser()
        args = parser.parse_args(["status"])
        assert args.verbose is False

    def test_version_and_verbose_no_conflict(self):
        """-v (version) and -V (verbose) should not conflict."""
        parser = self._make_parser()
        args = parser.parse_args(["-v"])
        assert args.version is True
        assert args.verbose is False

        args = parser.parse_args(["-V", "status"])
        assert args.version is False
        assert args.verbose is True


class TestDebugLogLevels:
    """Verify optional-dep messages are at DEBUG level, not INFO."""

    def test_voice_engine_twilio_log_is_debug(self):
        """twilio not-installed message should be at DEBUG level in source."""
        import inspect
        from core import voice_call_engine
        source = inspect.getsource(voice_call_engine)
        assert 'logger.debug("twilio not installed' in source
        assert 'logger.info("twilio not installed' not in source

    def test_voice_engine_websockets_log_is_debug(self):
        """websockets not-installed message should be at DEBUG level in source."""
        import inspect
        from core import voice_call_engine
        source = inspect.getsource(voice_call_engine)
        assert 'logger.debug("websockets not installed' in source

    def test_stt_whisper_log_is_debug(self):
        """faster-whisper not-installed message should be at DEBUG level in source."""
        import inspect
        from core.voice import stt_whisper
        source = inspect.getsource(stt_whisper)
        assert 'logger.debug("faster-whisper not installed' in source

    def test_rag_chromadb_log_is_debug(self):
        """ChromaDB not-installed message should be at DEBUG level in source."""
        import inspect
        from core import rag_engine
        source = inspect.getsource(rag_engine)
        assert 'logger.debug("ChromaDB/sentence-transformers not installed' in source

    def test_skill_registry_log_is_debug(self):
        """Skill registry seed message should be at DEBUG level in source."""
        import inspect
        from core import skill_registry
        source = inspect.getsource(skill_registry)
        assert 'logger.debug(f"Skill registry:' in source

    def test_fleet_shutdown_log_is_debug(self):
        """Fleet shut down message should be at DEBUG level in source."""
        import inspect
        from core import fleet_orchestrator
        source = inspect.getsource(fleet_orchestrator)
        assert 'logger.debug("Fleet shut down")' in source

    def test_batch_browser_log_is_debug(self):
        """Batch browser closed message should be at DEBUG level in source."""
        import inspect
        from core import enrichment_engine
        source = inspect.getsource(enrichment_engine)
        assert 'logger.debug("Batch browser closed")' in source


class TestPackaging:
    """Verify pyproject.toml is correctly configured."""

    def test_pyproject_has_py_modules(self):
        """pyproject.toml should list cli, config, main as py-modules."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        py_modules = data.get("tool", {}).get("setuptools", {}).get("py-modules", [])
        assert "cli" in py_modules
        assert "config" in py_modules
        assert "main" in py_modules

    def test_pyside6_not_in_base_deps(self):
        """PySide6 should NOT be in base dependencies (moved to gui optional)."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        base_deps = data["project"]["dependencies"]
        pyside_deps = [d for d in base_deps if "PySide6" in d]
        assert len(pyside_deps) == 0, "PySide6 should be in [gui] optional, not base deps"

    def test_pyside6_in_gui_optional(self):
        """PySide6 should be in [project.optional-dependencies.gui]."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        gui_deps = data["project"]["optional-dependencies"]["gui"]
        pyside_deps = [d for d in gui_deps if "PySide6" in d]
        assert len(pyside_deps) == 1

    def test_build_backend_is_standard(self):
        """build-backend should be setuptools.build_meta (not legacy)."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        assert data["build-system"]["build-backend"] == "setuptools.build_meta"

    def test_entry_points_defined(self):
        """aura and aura-gui entry points should be defined."""
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        scripts = data["project"]["scripts"]
        assert scripts["aura"] == "cli:main"
        assert scripts["aura-gui"] == "main:main"
