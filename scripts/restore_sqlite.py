import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.backend.db import get_db_path
from scripts.backup_sqlite import create_backup


def restore_backup(backup_path, target_path=None, backup_dir=None):
    backup = Path(backup_path)
    if not backup.exists():
        raise FileNotFoundError(f"Backup file does not exist: {backup}")
    if not backup.is_file():
        raise ValueError(f"Backup path is not a file: {backup}")

    target = Path(target_path) if target_path is not None else get_db_path()
    if not target.exists():
        raise FileNotFoundError(f"Target SQLite database file does not exist: {target}")

    pre_restore_backup = create_backup(target, backup_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, target)
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
