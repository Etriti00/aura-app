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
        """Create all tables if they don't exist."""
        Base.metadata.create_all(self.engine)

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
