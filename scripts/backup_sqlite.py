import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.db import PROJECT_ROOT, get_db_path, get_read_only_connection


SQLITE_HEADER = b"SQLite format 3\x00"


def resolve_backup_dir(backup_dir=None):
    configured = backup_dir or os.getenv("SQLITE_BACKUP_DIR") or "backups"
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def validate_sqlite_database(database_path):
    path = Path(database_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite database file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"SQLite database path is not a file: {path}")
    with path.open("rb") as file_obj:
        if file_obj.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
            raise ValueError(f"File is not a valid SQLite database: {path}")

    try:
        conn = get_read_only_connection(path)
        try:
            quick_check_rows = [row[0] for row in conn.execute("PRAGMA quick_check")]
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"SQLite validation failed for {path}: {exc}") from exc

    if quick_check_rows != ["ok"]:
        details = "; ".join(str(row) for row in quick_check_rows)
        raise ValueError(f"SQLite quick_check failed for {path}: {details}")
    return path


def copy_sqlite_database(source_path, target_path):
    source = validate_sqlite_database(source_path)
    target = Path(target_path)
    if source.resolve() == target.resolve():
        raise ValueError("SQLite source and target paths must be different.")

    target.parent.mkdir(parents=True, exist_ok=True)
    source_conn = get_read_only_connection(source)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
        target_conn.commit()
    finally:
        target_conn.close()
        source_conn.close()

    validate_sqlite_database(target)
    return target


def unique_backup_path(source, target_dir, stamp):
    candidate = target_dir / f"{source.stem}-{stamp}.sqlite3"
    suffix = 1
    while candidate.exists():
        candidate = target_dir / f"{source.stem}-{stamp}-{suffix}.sqlite3"
        suffix += 1
    return candidate


def create_backup(source_path=None, backup_dir=None, timestamp=None):
    source = Path(source_path) if source_path is not None else get_db_path()
    validate_sqlite_database(source)

    target_dir = resolve_backup_dir(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = unique_backup_path(source, target_dir, stamp)
    try:
        copy_sqlite_database(source, backup_path)
    except Exception:
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path


def main():
    parser = argparse.ArgumentParser(description="Backup the SQLite database.")
    parser.add_argument("--source", help="SQLite database path. Defaults to SQLITE_DB_PATH.")
    parser.add_argument("--backup-dir", help="Backup directory. Defaults to backups/.")
    args = parser.parse_args()

    backup_path = create_backup(args.source, args.backup_dir)
    print(f"SQLite backup created: {backup_path}")


if __name__ == "__main__":
    main()
