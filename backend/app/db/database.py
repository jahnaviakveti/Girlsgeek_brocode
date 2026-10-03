import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Determine database path (default to local sqlite file in data/ or root of backend)
DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
os.makedirs(DB_DIR, exist_ok=True)
SQLITE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR / 'vettora.db'}")

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False} if SQLITE_URL.startswith("sqlite") else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes tables on startup and ensures SQLite schema columns are up to date."""
    from . import models  # noqa
    Base.metadata.create_all(bind=engine)
    try:
        with engine.connect() as conn:
            res = conn.exec_driver_sql("PRAGMA table_info(evidence_records)")
            existing_cols = {row[1] for row in res.fetchall()}
            if existing_cols:
                missing_cols = [
                    ("source_document", "VARCHAR(255)"),
                    ("normalized_facts", "JSON"),
                    ("related_entity", "VARCHAR(255)"),
                    ("related_skill", "VARCHAR(255)"),
                    ("related_project", "VARCHAR(255)"),
                    ("related_experience", "VARCHAR(255)"),
                ]
                for col_name, col_type in missing_cols:
                    if col_name not in existing_cols:
                        conn.exec_driver_sql(f"ALTER TABLE evidence_records ADD COLUMN {col_name} {col_type}")
                conn.commit()
    except Exception:
        pass

