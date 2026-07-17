"""SQLAlchemy database engine and session configuration."""

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class IncompatibleDatabaseSchemaError(RuntimeError):
    """Raised when an existing database is missing expected columns."""

settings = get_settings()

connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.debug,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        """Enable foreign key support for SQLite connections."""
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _verify_schema() -> None:
    """Detect a stale existing schema and raise a clear developer error.

    ``create_all`` creates missing tables but never alters existing ones, so an
    old database file (e.g. missing a column added in a later phase) would only
    surface as a confusing SQL error at query time. Instead we compare each
    model's columns against the live table and fail fast with reset guidance.
    Phase 4 intentionally does not perform destructive automatic migrations;
    Alembic is the recommended production path.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # create_all will create it
        actual_columns = {col["name"] for col in inspector.get_columns(table_name)}
        expected_columns = {column.name for column in table.columns}
        missing = expected_columns - actual_columns
        if missing:
            raise IncompatibleDatabaseSchemaError(
                f"The '{table_name}' table is missing columns {sorted(missing)}. "
                "Your local development database is out of date. Reset it with:\n"
                "  rm linkedin_jobs.db\n"
                "  uvicorn app.main:app --reload\n"
                "(No automatic destructive migration is performed. Use Alembic "
                "for production schema migrations.)"
            )


def init_db() -> None:
    """Create all database tables, verifying an existing schema is compatible."""
    # Import models so they register with Base.metadata before create_all.
    import app.models  # noqa: F401

    _verify_schema()
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
