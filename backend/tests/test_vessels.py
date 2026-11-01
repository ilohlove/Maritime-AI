import pytest
from alembic import command
from alembic.config import Config
from app.main import create_app
from app.services.ai import AIProvider, MockAIProvider
from fastapi.testclient import TestClient
from sqlalchemy import inspect


# Synthetic test identifiers; these records do not describe a real vessel.
def test_startup_and_empty_database(client):
    assert client.get("/api/health").json() == {
        "status": "ok",
        "ai_provider": "llama.cpp-local",
    }
    assert client.get("/api/vessels").json() == []


def test_create_retrieve_update(client):
    response = client.post(
        "/api/vessels",
        json={
            "vessel_name": "SYNTHETIC TEST VESSEL",
            "length_overall": "123.456",
            "gross_tonnage": 7000,
        },
    )
    assert response.status_code == 201
    vessel = response.json()
    assert vessel["length_overall"] == "123.456"
    assert vessel["imo_number"] is None
    assert vessel["created_at"].endswith("Z")
    assert vessel["updated_at"].endswith("Z")
    assert (
        vessel["field_provenance"]["vessel_name"]["verification_status"] == "unverified"
    )
    original_metadata = vessel["field_provenance"]["length_overall"]
    assert client.get(f"/api/vessels/{vessel['id']}").json() == vessel
    updated = client.patch(
        f"/api/vessels/{vessel['id']}",
        json={"vessel_name": "SYNTHETIC UPDATED", "flag": "Test flag"},
    )
    assert updated.status_code == 200
    assert updated.json()["vessel_name"] == "SYNTHETIC UPDATED"
    assert updated.json()["gross_tonnage"] == 7000
    assert updated.json()["field_provenance"]["length_overall"] == original_metadata


@pytest.mark.parametrize(
    "payload",
    [
        {"imo_number": "1234560"},
        {"imo_number": "123"},
        {"mmsi": "1234"},
        {"mmsi": "abcdefghi"},
        {"year_built": 1700},
        {"year_built": 2000.5},
        {"length_overall": "-1"},
        {"length_overall": "1.1234"},
        {"main_engine_power": "NaN"},
        {"summer_draft": "Infinity"},
        {"gross_tonnage": 100, "net_tonnage": 101},
        {"length_overall": "10", "length_between_perpendiculars": "11"},
        {"vessel_name": "x" * 201},
        {"unexpected": "field"},
        {"provenance": {"fake": {}}},
        {"provenance": {"vessel_name": {}}},
        {
            "vessel_name": "test",
            "provenance": {
                "vessel_name": {
                    "extraction_method": "ai_extracted",
                    "verification_status": "verified",
                }
            },
        },
    ],
)
def test_validation(client, payload):
    assert client.post("/api/vessels", json=payload).status_code == 422
    assert client.get("/api/vessels").json() == []


def test_imo_checksum_and_leading_zero_mmsi(client):
    # Syntactically valid checksum fixture, not asserted to be an assigned IMO.
    response = client.post(
        "/api/vessels", json={"imo_number": "0000000", "mmsi": "001000000"}
    )
    assert response.status_code == 201
    assert response.json()["mmsi"] == "001000000"


def test_unknown_values_and_clear(client):
    vessel = client.post(
        "/api/vessels", json={"vessel_name": "   ", "flag": "TEST"}
    ).json()
    assert vessel["vessel_name"] is None
    updated = client.patch(f"/api/vessels/{vessel['id']}", json={"flag": None}).json()
    assert updated["flag"] is None
    assert "flag" not in updated["field_provenance"]
    assert client.post("/api/vessels", json={}).status_code == 201


def test_import_and_explicit_human_verification(client):
    vessel = client.post(
        "/api/vessels",
        json={
            "flag": "Synthetic",
            "provenance": {
                "flag": {
                    "extraction_method": "imported",
                    "source_document": "synthetic-record",
                    "last_updated": "2000-01-01T00:00:00Z",
                }
            },
        },
    ).json()
    meta = vessel["field_provenance"]["flag"]
    assert meta["extraction_method"] == "imported"
    assert meta["verification_status"] == "unverified"
    assert not meta["last_updated"].startswith("2000")
    updated = client.patch(
        f"/api/vessels/{vessel['id']}",
        json={
            "flag": "Synthetic",
            "provenance": {"flag": {"verification_status": "verified"}},
        },
    ).json()
    assert updated["field_provenance"]["flag"]["verification_status"] == "verified"
    changed = client.patch(
        f"/api/vessels/{vessel['id']}", json={"flag": "Changed"}
    ).json()
    assert changed["field_provenance"]["flag"]["verification_status"] == "unverified"


def test_patch_validates_merged_state_and_does_not_mutate_on_failure(client):
    vessel = client.post(
        "/api/vessels", json={"gross_tonnage": 100, "net_tonnage": 80}
    ).json()
    path = f"/api/vessels/{vessel['id']}"
    assert client.patch(path, json={"gross_tonnage": 50}).status_code == 422
    assert client.get(path).json()["gross_tonnage"] == 100


def test_missing_vessel(client):
    assert client.get("/api/vessels/missing").status_code == 404
    assert client.patch("/api/vessels/missing", json={}).status_code == 404


def test_persistence_after_restart(configured_app):
    app, settings = configured_app
    with TestClient(app) as first:
        vessel = first.post(
            "/api/vessels",
            json={"vessel_name": "SYNTHETIC PERSISTENCE", "summer_draft": "6.125"},
        ).json()
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/vessels/{vessel['id']}").json() == vessel
        assert len(restarted.get("/api/vessels").json()) == 1


def test_multiple_profiles_have_distinct_ids(client):
    first = client.post("/api/vessels", json={}).json()
    second = client.post("/api/vessels", json={}).json()
    assert first["id"] != second["id"]
    assert len(client.get("/api/vessels").json()) == 2


def test_local_browser_security(client):
    assert (
        client.post(
            "/api/vessels", json={}, headers={"origin": "https://untrusted.invalid"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/vessels",
            content="vessel_name=test",
            headers={"content-type": "application/x-www-form-urlencoded"},
        ).status_code
        == 415
    )
    response = client.options(
        "/api/vessels",
        headers={
            "origin": "http://127.0.0.1:5173",
            "access-control-request-method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    blocked = client.options(
        "/api/vessels",
        headers={
            "origin": "https://untrusted.invalid",
            "access-control-request-method": "POST",
        },
    )
    assert blocked.status_code == 400


def test_migration_repeatability_and_downgrade(configured_app):
    app, _ = configured_app
    config = Config("alembic.ini")
    with app.state.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert "vessels" in inspect(connection).get_table_names()
        command.downgrade(config, "base")
        assert "vessels" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert "vessels" in inspect(connection).get_table_names()


def test_mock_is_explicitly_not_advice():
    provider: AIProvider = MockAIProvider()
    assert "Mock AI Provider" in provider.respond("What should I do?")
    assert "No maritime advice" in provider.respond("What should I do?")
