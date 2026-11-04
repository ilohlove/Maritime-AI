"""Generate a backend password hash without putting the password in shell history."""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.auth import hash_password

if __name__ == "__main__":
    password = getpass.getpass("New private MVP password (12+ characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    print(hash_password(password))
