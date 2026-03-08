"""
Aura — Database Manager
SQLite engine with WAL mode, session factory, and data seeding.
"""

import threading

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from config import DB_PATH
from database.schema import Base, Settings, Skill


class DatabaseManager:
    """Manages SQLite database connection, sessions, and initialization."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        # Enable WAL mode for better concurrent read performance
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        self.SessionFactory = sessionmaker(bind=self.engine)

    @contextmanager
    def session_scope(self) -> Session:
        """Provide a transactional scope around a series of operations.
        Serializes writes via a threading lock to prevent SQLite 'database is locked' errors.
        """
        with self._write_lock:
            session = self.SessionFactory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

    def init_db(self):
        """Create all tables if they don't exist, then migrate existing tables."""
        Base.metadata.create_all(self.engine)
        self._migrate_schema()

    def _migrate_schema(self):
        """Add missing columns to existing tables (SQLite ALTER TABLE)."""
        from sqlalchemy import text, inspect

        inspector = inspect(self.engine)

        # ─── Skills table: enhanced fields (Claude Agent SDK-inspired) ──
        if "skills" in inspector.get_table_names():
            existing = {col["name"] for col in inspector.get_columns("skills")}
            new_columns = [
                ("description", "TEXT DEFAULT ''"),
                ("instructions", "TEXT DEFAULT ''"),
                ("input_schema", "TEXT DEFAULT '{}'"),
                ("output_schema", "TEXT DEFAULT '{}'"),
                ("examples", "TEXT DEFAULT '[]'"),
                ("category", "VARCHAR(50) DEFAULT 'general'"),
                ("version", "VARCHAR(20) DEFAULT '1.0'"),
                ("capabilities", "TEXT DEFAULT '[]'"),
                ("tags", "TEXT DEFAULT '[]'"),
            ]
            with self.engine.connect() as conn:
                for col_name, col_def in new_columns:
                    if col_name not in existing:
                        conn.execute(text(
                            f"ALTER TABLE skills ADD COLUMN {col_name} {col_def}"
                        ))
                conn.commit()

        # ─── AgentTask: token tracking + dedup (Features 1+3) ────────
        if "agent_tasks" in inspector.get_table_names():
            existing_at = {col["name"] for col in inspector.get_columns("agent_tasks")}
            at_columns = [
                ("input_tokens", "INTEGER DEFAULT 0"),
                ("output_tokens", "INTEGER DEFAULT 0"),
                ("context_hash", "TEXT"),
            ]
            with self.engine.connect() as conn:
                for col_name, col_def in at_columns:
                    if col_name not in existing_at:
                        conn.execute(text(
                            f"ALTER TABLE agent_tasks ADD COLUMN {col_name} {col_def}"
                        ))
                conn.commit()


    def seed_defaults(self):
        """Insert default Settings row and built-in Skills if not present."""
        from database.seed_skills import seed_defaults
        seed_defaults(self)

    def migrate_schema(self):
        """Add new columns to existing tables for backward compatibility."""
        from database.migrations import migrate_schema
        migrate_schema(self.db_path)

    def seed_default_agents(self):
        """Insert or update default agents with rich personas."""
        from database.seed_agents import seed_default_agents
        seed_default_agents(self)

    def _set_hierarchy(self):
        """Set rank and reports_to for all seed agents."""
        from database.seed_agents import _set_hierarchy
        _set_hierarchy(self)

    def get_settings(self) -> Settings:
        """Get the singleton Settings row."""
        with self.session_scope() as session:
            settings = session.query(Settings).first()
            if settings:
                session.expunge(settings)
            return settings
