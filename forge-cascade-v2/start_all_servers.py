"""
Forge V3 - Start All Servers

Starts all three API servers:
- Cascade API (port 8001) - Core engine
- Compliance API (port 8002) - GDPR/compliance features
- Virtuals API (port 8003) - Blockchain/tokenization integration

Usage:
    python start_all_servers.py
    python start_all_servers.py --cascade-only
    python start_all_servers.py --no-compliance
"""

import argparse
import subprocess
import sys
import time
import os
import signal
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.absolute()

# Server configurations
SERVERS = {
    "cascade": {
        "name": "Cascade API",
        "port": 8001,
        "command": [sys.executable, "-m", "uvicorn", "forge.api.app:app", "--host", "0.0.0.0", "--port", "8001"],
        "cwd": SCRIPT_DIR,
        "health_url": "http://localhost:8001/health",
    },
    "compliance": {
        "name": "Compliance API",
        "port": 8002,
        "command": [sys.executable, str(SCRIPT_DIR / "run_compliance.py")],
        "cwd": SCRIPT_DIR,
        "health_url": "http://localhost:8002/health",
    },
    "virtuals": {
        "name": "Virtuals API",
        "port": 8003,
        "command": [sys.executable, str(SCRIPT_DIR / "run_virtuals.py")],
        "cwd": SCRIPT_DIR,
        "health_url": "http://localhost:8003/health",
    },
}

processes = {}


def check_port_available(port: int) -> bool:
    """Check if a port is available."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def wait_for_server(url: str, timeout: int = 60) -> bool:
    """Wait for a server to become healthy."""
    import urllib.request
    import urllib.error

    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionRefusedError, OSError):
            pass
        time.sleep(0.5)
    return False


def start_server(name: str, config: dict) -> subprocess.Popen | None:
    """Start a single server."""
    port = config["port"]

    if not check_port_available(port):
        print(f"  [!] Port {port} is already in use - {config['name']} may already be running")
        return None

    print(f"  Starting {config['name']} on port {port}...")

    # Start the process
    process = subprocess.Popen(
        config["command"],
        cwd=config["cwd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )

    # Wait for it to become healthy
    if wait_for_server(config["health_url"], timeout=30):
        print(f"  [OK] {config['name']} started successfully (PID: {process.pid})")
        return process
    else:
        print(f"  [FAIL] {config['name']} failed to start")
        process.terminate()
        return None


def stop_all():
    """Stop all running server processes."""
    print("\nStopping servers...")
    for name, process in processes.items():
        if process and process.poll() is None:
            print(f"  Stopping {SERVERS[name]['name']}...")
            if sys.platform == "win32":
                process.terminate()
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
    print("All servers stopped.")


def signal_handler(signum, frame):
    """Handle interrupt signals."""
    stop_all()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Start Forge V3 API servers")
    parser.add_argument("--cascade-only", action="store_true", help="Start only the Cascade API")
    parser.add_argument("--no-cascade", action="store_true", help="Don't start Cascade API")
    parser.add_argument("--no-compliance", action="store_true", help="Don't start Compliance API")
    parser.add_argument("--no-virtuals", action="store_true", help="Don't start Virtuals API")
    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 60)
    print("FORGE V3 - Starting API Servers")
    print("=" * 60)

    # Determine which servers to start
    servers_to_start = []

    if args.cascade_only:
        servers_to_start = ["cascade"]
    else:
        if not args.no_cascade:
            servers_to_start.append("cascade")
        if not args.no_compliance:
            servers_to_start.append("compliance")
        if not args.no_virtuals:
            servers_to_start.append("virtuals")

    if not servers_to_start:
        print("No servers selected to start!")
        return 1

    # Start the servers
    failed = []
    for name in servers_to_start:
        config = SERVERS[name]
        process = start_server(name, config)
        if process:
            processes[name] = process
        else:
            if check_port_available(config["port"]):
                failed.append(name)

    print()
    print("=" * 60)
    print("SERVER STATUS")
    print("=" * 60)

    for name in servers_to_start:
        config = SERVERS[name]
        status = "RUNNING" if name in processes or not check_port_available(config["port"]) else "FAILED"
        symbol = "[OK]" if status == "RUNNING" else "[FAIL]"
        print(f"  {symbol} {config['name']:20} http://localhost:{config['port']}")

    if failed:
        print(f"\nWarning: {len(failed)} server(s) failed to start: {', '.join(failed)}")

    print()
    print("Press Ctrl+C to stop all servers...")
    print()

    # Keep the script running
    try:
        while True:
            # Check if any processes have died
            for name, process in list(processes.items()):
                if process and process.poll() is not None:
                    print(f"[!] {SERVERS[name]['name']} has stopped unexpectedly")
                    del processes[name]

            if not processes:
                print("All servers have stopped.")
                break

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
