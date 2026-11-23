"""Start the Concall API and React UI with one command."""

import shutil
import subprocess
import sys
import threading
import time
import venv
import webbrowser
import os
import urllib.request
import socket
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PIPELINE = ROOT / "concall-pipeline"
CLIENT = ROOT / "concall-client"
VENV = PIPELINE / ".venv"
ENV_FILE = PIPELINE / ".env"


def read_env_value(path: Path, name: str) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip("\"'")
    return ""


def run_checked(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}")


def stream_output(process: subprocess.Popen, prefix: str) -> None:
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        try:
            print(f"[{prefix}] {line}", flush=True)
        except UnicodeEncodeError:
            encoding = getattr(sys.stdout, "encoding", None) or "ascii"
            safe_line = line.encode(encoding, errors="replace").decode(encoding, errors="replace")
            print(f"[{prefix}] {safe_line}", flush=True)


def wait_until_ready(url: str, process: subprocess.Popen, timeout: float = 20) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 400:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def main() -> int:
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    os.environ.setdefault("PYTHONUTF8", "1")

    api_key = read_env_value(ENV_FILE, "LLM_API_KEY")
    placeholder_values = {"", "your_api_key", "your-api-key", "change-me", "replace-me"}
    if not api_key or api_key.lower() in placeholder_values or "here" in api_key.lower():
        print("LLM_API_KEY is not configured. Starting in sample-preview mode.")

    if sys.platform == "win32":
        python = VENV / "Scripts" / "python.exe"
    else:
        python = VENV / "bin" / "python"

    if not python.exists():
        print("Creating Python virtual environment...")
        venv.EnvBuilder(with_pip=True).create(VENV)

    if not (PIPELINE / ".venv-ready").exists():
        print("Installing Python dependencies...")
        run_checked([str(python), "-m", "pip", "install", "-r", "requirements.txt"], PIPELINE)

    npm = shutil.which("npm")
    if not npm:
        npm = shutil.which("npm.cmd")
    if not npm:
        print("Cannot start: npm was not found on PATH.")
        print("Install Node.js, then run this command again.")
        return 1

    if not (CLIENT / "node_modules").exists():
        print("Installing frontend dependencies...")
        run_checked([npm, "install"], CLIENT)

    (PIPELINE / ".venv-ready").touch()

    api = None
    if port_is_open("127.0.0.1", 8000):
        print("Reusing backend at http://localhost:8000")
    else:
        print("Starting backend at http://localhost:8000")
        api = subprocess.Popen(
            [str(python), "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=PIPELINE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if not wait_until_ready("http://127.0.0.1:8000/api/summaries", api):
            api.terminate()
            raise RuntimeError("Backend did not become ready on port 8000")

    ui = None
    if port_is_open("127.0.0.1", 5173):
        print("Reusing frontend at http://localhost:5173")
    else:
        print("Starting frontend at http://localhost:5173")
        ui = subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
            cwd=CLIENT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if not wait_until_ready("http://127.0.0.1:5173", ui):
            ui.terminate()
            if api is not None:
                api.terminate()
            raise RuntimeError("Frontend did not become ready on port 5173")

    threads = []
    if api is not None:
        threads.append(threading.Thread(target=stream_output, args=(api, "api"), daemon=True))
    if ui is not None:
        threads.append(threading.Thread(target=stream_output, args=(ui, "ui"), daemon=True))
    for thread in threads:
        thread.start()

    webbrowser.open("http://localhost:5173")
    print("Both services are running. Press Ctrl+C to stop.")

    try:
        while True:
            if api is not None and api.poll() is not None:
                raise RuntimeError(f"Backend stopped with exit code {api.returncode}")
            if ui is not None and ui.poll() is not None:
                raise RuntimeError(f"Frontend stopped with exit code {ui.returncode}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        for process in (api, ui):
            if process is not None and process.poll() is None:
                process.terminate()
        for process in (api, ui):
            if process is None:
                continue
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
