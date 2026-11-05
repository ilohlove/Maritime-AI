"""Generate a backend password hash without putting the password in shell history."""

import getpass
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.auth import hash_password


def main():
    # getpass otherwise falls back to echoed stdin when hidden input is unavailable.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            password = getpass.getpass(
                "New private MVP password (12–256 characters): "
            )
            confirmation = getpass.getpass("Confirm password: ")
        except getpass.GetPassWarning:
            raise SystemExit(
                "Hidden password input is unavailable. Use a local interactive terminal."
            ) from None
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    print(hash_password(password))


if __name__ == "__main__":
    main()
