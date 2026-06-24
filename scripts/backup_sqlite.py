import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path

from apps.backend.db import PROJECT_ROOT, get_db_path


def resolve_backup_dir(backup_dir=None):
    configured = backup_dir or os.getenv("SQLITE_BACKUP_DIR") or "backups"
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def create_backup(source_path=None, backup_dir=None, timestamp=None):
    source = Path(source_path) if source_path is not None else get_db_path()
    if not source.exists():
        raise FileNotFoundError(f"SQLite database file does not exist: {source}")

    target_dir = resolve_backup_dir(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = target_dir / f"{source.stem}-{stamp}.sqlite3"
    shutil.copy2(source, backup_path)
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
