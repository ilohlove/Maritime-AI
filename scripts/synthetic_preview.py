"""Run Task 01 with a separate, clearly synthetic, persistent preview database."""

import argparse
import os
import subprocess
import sys
from urllib.parse import urlsplit

from dev import ROOT, main as run_workspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        help="Exact frontend origin, e.g. http://192.168.1.20:5173 or an authenticated cloud preview origin",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Frontend bind address; backend always stays on loopback"
    )
    args = parser.parse_args()
    origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
    if args.host != "127.0.0.1" and not args.origin:
        parser.error("A non-loopback frontend requires an explicit --origin")
    if args.origin:
        url = urlsplit(args.origin)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.path or url.query or url.fragment or url.username or url.password
        ):
            parser.error("--origin must contain only scheme, host and optional port")
        origins.append(args.origin)
        # Vite supports one extra trusted hostname without disabling host checks.
        os.environ["__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS"] = url.hostname

    directory = ROOT / ".preview-synthetic"
    marker = directory / "SYNTHETIC_ONLY"
    if directory.exists() and not marker.exists() and any(directory.iterdir()):
        parser.error("Refusing to use an existing unmarked preview data directory")
    directory.mkdir(exist_ok=True)
    marker.write_text("Synthetic UI review only. Never enter real vessel data.\n")
    # Override any inherited operational database configuration.
    os.environ["MARITIME_DATA_DIR"] = str(directory)
    os.environ["MARITIME_DATABASE_URL"] = f"sqlite:///{(directory / 'maritime.db').as_posix()}"
    os.environ["MARITIME_ALLOWED_ORIGINS"] = ",".join(origins)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT / "backend", check=True,
    )

    from app.core.config import Settings
    from app.db.session import create_database
    from app.schemas.vessel import VesselWrite
    from app.services.vessels import list_vessels, save_vessel

    engine, sessions = create_database(Settings().database_url)
    try:
        with sessions() as session:
            if not list_vessels(session):
                save_vessel(session, VesselWrite(
                    vessel_name="SYNTHETIC PREVIEW VESSEL — TEST DATA",
                    flag="SYNTHETIC FLAG", call_sign="TEST ONLY",
                    port_of_registry="SYNTHETIC PORT",
                    vessel_type="Synthetic bulk carrier",
                    year_built=2020, length_overall="180.000",
                    length_between_perpendiculars="172.000", breadth_moulded="30.000",
                    depth_moulded="16.000", summer_draft="10.500",
                    gross_tonnage=25000, net_tonnage=15000,
                    summer_deadweight="40000.000",
                    main_engine_manufacturer="SYNTHETIC MAKER",
                    main_engine_model="TEST ENGINE", main_engine_power="7000.000",
                ))
    finally:
        engine.dispose()
    print("SYNTHETIC PREVIEW ONLY — no real vessel data. Edits survive reload/restart.", flush=True)
    print(f"Preview database: {directory / 'maritime.db'}", flush=True)
    print(f"Open: {args.origin or origins[0]}", flush=True)
    run_workspace(frontend_host=args.host)


if __name__ == "__main__":
    main()
