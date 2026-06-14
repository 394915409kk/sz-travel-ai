import sqlite3
import os
from pathlib import Path

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
