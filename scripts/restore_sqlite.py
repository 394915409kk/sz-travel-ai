import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.db import get_db_path
from scripts.backup_sqlite import (
    copy_sqlite_database,
    create_backup,
    validate_sqlite_database,
)


def restore_backup(backup_path, target_path=None, backup_dir=None):
    backup = validate_sqlite_database(backup_path)

    target = Path(target_path) if target_path is not None else get_db_path()
    if not target.exists():
        raise FileNotFoundError(f"Target SQLite database file does not exist: {target}")
    if backup.resolve() == target.resolve():
        raise ValueError("Backup and target paths must be different.")

    pre_restore_backup = create_backup(target, backup_dir)
    try:
        copy_sqlite_database(backup, target)
    except Exception:
        copy_sqlite_database(pre_restore_backup, target)
        raise
    return {
        "restored_from": backup,
        "restored_to": target,
        "pre_restore_backup": pre_restore_backup,
    }


def main():
    parser = argparse.ArgumentParser(description="Restore the SQLite database from a backup.")
    parser.add_argument("backup_path", help="Backup file path to restore from.")
    parser.add_argument("--target", help="Target SQLite database path. Defaults to SQLITE_DB_PATH.")
    parser.add_argument("--backup-dir", help="Where to place the pre-restore backup.")
    args = parser.parse_args()

    result = restore_backup(args.backup_path, args.target, args.backup_dir)
    print(f"Pre-restore backup created: {result['pre_restore_backup']}")
    print(f"SQLite database restored: {result['restored_to']}")


if __name__ == "__main__":
    main()
