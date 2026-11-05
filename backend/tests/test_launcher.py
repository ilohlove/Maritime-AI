"""Launcher configuration, not a claim about Render's ingress addresses."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def launcher(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts" / "start_backend.py"
    spec = importlib.util.spec_from_file_location("backend_launcher", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "Settings",
        lambda: SimpleNamespace(
            environment="production", https_transport="trusted-proxy"
        ),
    )
    monkeypatch.setattr(module.uvicorn, "run", Mock())
    for name in ("MARITIME_BIND_HOST", "MARITIME_TRUSTED_PROXY_IPS", "PORT"):
        monkeypatch.delenv(name, raising=False)
    return module


def test_render_bind_and_platform_port_are_forwarded(launcher, monkeypatch):
    monkeypatch.setenv("MARITIME_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "18763")
    # TEST-NET address: a simulated ingress, never a Render address claim.
    monkeypatch.setenv("MARITIME_TRUSTED_PROXY_IPS", "192.0.2.10")
    launcher.main()
    kwargs = launcher.uvicorn.run.call_args.kwargs
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["port"] == 18763
    assert kwargs["workers"] == 1
    assert kwargs["proxy_headers"] is True
    assert kwargs["forwarded_allow_ips"] == "192.0.2.10"


@pytest.mark.parametrize("proxies", ["", "*", "0.0.0.0/0", "::/0", "render.com"])
def test_no_production_listener_without_valid_explicit_trust(
    launcher, monkeypatch, proxies
):
    monkeypatch.setenv("MARITIME_TRUSTED_PROXY_IPS", proxies)
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    # Render metadata is not proof of a particular request's origin/scheme.
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(ValueError):
        launcher.main()
    launcher.uvicorn.run.assert_not_called()


def test_local_defaults_keep_loopback_and_disable_header_trust(launcher, monkeypatch):
    monkeypatch.setattr(
        launcher,
        "Settings",
        lambda: SimpleNamespace(
            environment="development", https_transport="trusted-proxy"
        ),
    )
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    launcher.main()
    kwargs = launcher.uvicorn.run.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 8000
    assert kwargs["proxy_headers"] is False
    assert kwargs["forwarded_allow_ips"] == ""


def test_signed_gateway_disables_all_uvicorn_proxy_header_trust(launcher, monkeypatch):
    monkeypatch.setattr(
        launcher,
        "Settings",
        lambda: SimpleNamespace(
            environment="production", https_transport="signed-gateway"
        ),
    )
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    launcher.main()
    kwargs = launcher.uvicorn.run.call_args.kwargs
    assert kwargs["proxy_headers"] is False
    assert kwargs["forwarded_allow_ips"] == ""
