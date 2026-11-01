"""Start the local workspace from any directory; run with the backend virtualenv."""

import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(frontend_host="127.0.0.1"):
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise SystemExit("npm is required. Install Node.js 22.12+ first.")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT / "backend",
        check=True,
    )
    processes = []

    def stop(_signal, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    process_options = {"start_new_session": True} if os.name != "nt" else {}
    try:
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT / "backend",
            **process_options,
        )
        processes.append(backend)
        local_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(100):
            if backend.poll() is not None:
                raise RuntimeError("Backend failed to start; check its output above.")
            try:
                with local_http.open(
                    "http://127.0.0.1:8000/api/health", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Backend readiness check timed out.")
        processes.append(
            subprocess.Popen(
                [npm, "run", "dev", "--", "--host", frontend_host],
                cwd=ROOT / "frontend",
                **process_options,
            )
        )
        print("Workspace: http://127.0.0.1:5173 (Ctrl+C to stop)", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.3)
        raise RuntimeError("A development service exited. Check its output above.")
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                    )
                else:
                    os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
