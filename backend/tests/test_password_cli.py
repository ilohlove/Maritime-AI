"""The local generator must never fall back to visible password input."""

import getpass
import importlib.util
import warnings
from pathlib import Path

import pytest
from app.services.auth import validate_password_hash, verify_password


@pytest.fixture
def password_cli():
    path = Path(__file__).resolve().parents[2] / "scripts" / "hash_password.py"
    spec = importlib.util.spec_from_file_location("password_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_outputs_only_a_valid_hash(password_cli, monkeypatch, capsys):
    password = "synthetic-local-cli-password"
    monkeypatch.setattr(getpass, "getpass", lambda prompt: password)
    password_cli.main()
    encoded = capsys.readouterr().out.strip()
    validate_password_hash(encoded)
    assert verify_password(password, encoded)
    assert password not in encoded


@pytest.mark.parametrize("warning_on", [1, 2])
def test_generator_refuses_echo_fallback(
    password_cli, monkeypatch, capsys, warning_on
):
    calls = 0

    def hidden_input(prompt):
        nonlocal calls
        calls += 1
        if calls == warning_on:
            warnings.warn("Cannot control echo", getpass.GetPassWarning)
            pytest.fail("A password would have been read with echo enabled")
        return "synthetic-local-cli-password"

    monkeypatch.setattr(getpass, "getpass", hidden_input)
    with pytest.raises(SystemExit, match="local interactive terminal"):
        password_cli.main()
    assert capsys.readouterr().out == ""


def test_generator_rejects_mismatched_confirmation(password_cli, monkeypatch, capsys):
    answers = iter(["synthetic-local-cli-password", "different-confirmation"])
    monkeypatch.setattr(getpass, "getpass", lambda prompt: next(answers))
    with pytest.raises(SystemExit, match="Passwords do not match"):
        password_cli.main()
    assert capsys.readouterr().out == ""
