import sqlite3
import os
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
DEFAULT_DB_PATH = BASE_DIR / "travel_products.db"


def get_db_path() -> Path:
    configured_path = os.getenv("SQLITE_DB_PATH")

    if not configured_path:
        return DEFAULT_DB_PATH

    db_path = Path(configured_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    return db_path


def get_connection():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_read_only_connection(db_path=None):
    path = Path(db_path) if db_path is not None else get_db_path()
    if not path.exists():
        raise FileNotFoundError(f"SQLite database file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"SQLite database path is not a file: {path}")

    encoded_path = quote(path.resolve().as_posix(), safe="/")
    conn = sqlite3.connect(f"file:{encoded_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn
