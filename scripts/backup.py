"""Operator-only consistent SQLite backup plus immutable referenced originals.

Example: python scripts/backup.py --database /data/maritime.db
         --documents /data/originals --output /backups/new-snapshot
Use an encrypted backup destination. No network or public API is involved.
"""

import argparse
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID


def backup(database: Path, documents: Path, output: Path):
    if not database.is_file() or not documents.is_dir():
        raise ValueError("Database and original-document directory must exist")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    destination = output / "maritime.db"
    with (
        closing(
            sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        ) as source,
        closing(sqlite3.connect(destination)) as target,
    ):
        source.backup(target)
        # Restored snapshots must never resurrect a session. Budget/rate rows stay.
        target.execute("DELETE FROM auth_sessions")
        names = [
            row[0]
            for row in target.execute(
                "SELECT original_path FROM documents WHERE original_path IS NOT NULL"
            )
        ]
        target.commit()
        if (
            target.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            or target.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise RuntimeError("Backup integrity validation failed")
    destination.chmod(0o600)
    originals = output / "originals"
    originals.mkdir(mode=0o700)
    for name in names:
        if Path(name).name != name or not name.endswith(".bin"):
            raise ValueError("Invalid stored original filename")
        UUID(name[:-4])
        shutil.copyfile(documents / name, originals / name)
        (originals / name).chmod(0o600)
    (output / "COMPLETE").write_text(
        "SQLite integrity and originals copied. Sessions revoked in snapshot.\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    backup(arguments.database, arguments.documents, arguments.output)
    print("Backup complete. Protect the snapshot as sensitive data.")
