"""Explicit test-only bootstrap: isolated temporary data, production auth/TLS, no AI.

Never use operational documents. No cloud resources are created by this script.
A new directory is created every start; no existing database is reset or removed.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.core.disposable import DISPOSABLE_ACK
from app.db.session import create_database
from start_backend import main as start_backend


def main():
    if (
        os.environ.get("MARITIME_ENV") != "production"
        or os.environ.get("MARITIME_DISPOSABLE_TEST_MODE") != "true"
        or os.environ.get("MARITIME_DISPOSABLE_ACK") != DISPOSABLE_ACK
        or os.environ.get("MARITIME_STORAGE_PERSISTENT") != "false"
    ):
        raise ValueError(
            "Explicit production-secured disposable flags and data-loss acknowledgement are required"
        )
    with tempfile.TemporaryDirectory(prefix="maritime-disposable-") as directory:
        root = Path(directory)
        os.environ["MARITIME_DISPOSABLE_ROOT"] = directory
        os.environ["MARITIME_DATABASE_URL"] = f"sqlite:///{root / 'maritime.db'}"
        os.environ["MARITIME_DOCUMENTS_DIR"] = str(root / "originals")
        settings = (
            Settings()
        )  # Validate every production guard before migration/listening.
        engine, _ = create_database(settings.database_url)
        config = Config(str(ROOT / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
        try:
            with engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        finally:
            engine.dispose()
        start_backend()


if __name__ == "__main__":
    main()
