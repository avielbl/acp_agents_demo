"""Convenience script: start all 3 ACP agent microservices as subprocesses."""
import os
import subprocess
import sys
import time

import httpx


SERVICES = [
    ("Planner",   "agents/planner_service.py",   "http://127.0.0.1:8001/ping"),
    ("Executor",  "agents/executor_service.py",  "http://127.0.0.1:8002/ping"),
    ("Validator", "agents/validator_service.py", "http://127.0.0.1:8003/ping"),
]


def wait_healthy(name: str, url: str, timeout: int = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                print(f"  ✓ {name} is up ({url})")
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{name} did not become healthy within {timeout}s")


def main() -> None:
    processes = []
    python = sys.executable
    env = os.environ.copy()
    # Ensure current directory is in PYTHONPATH so 'src' is importable
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")

    print("Starting ACP agent microservices...\n")
    for name, script, _ in SERVICES:
        p = subprocess.Popen([python, script], env=env)
        processes.append((name, p))
        print(f"  → {name} service started (PID {p.pid})")

    print("\nWaiting for services to be healthy...")
    for name, _, ping_url in SERVICES:
        wait_healthy(name, ping_url)

    print("\nAll 3 agent services are up and healthy.")
    print("Press Ctrl+C to stop all services.\n")

    try:
        for _, p in processes:
            p.wait()
    except KeyboardInterrupt:
        print("\nShutting down all agent services...")
        for name, p in processes:
            p.terminate()
            print(f"  ✗ {name} stopped")


if __name__ == "__main__":
    main()
