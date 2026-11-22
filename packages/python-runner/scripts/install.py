#!/usr/bin/env python3
# Installs Python packages into Run Python's own environment: a venv in its data folder, used only by
# Run Python, never this Mac's Python. Runs only when you click "Install …" under a run that needed it.
# This is the one Run Python script that may reach the internet (to download from PyPI).
import json, os, re, subprocess, sys

def progress(line):
    print("progress: " + line, file=sys.stderr, flush=True)

data = json.load(sys.stdin)
wanted = (data.get("action") or {}).get("packages", "")
names = [n for n in wanted.split() if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,60}", n)]
if not names:
    print(json.dumps({"console": "Nothing to install.", "failed": True}))
    sys.exit()
venv = os.path.join(os.environ.get("HOME", "."), "venv")
python = os.path.join(venv, "bin", "python")
if not os.path.exists(python):
    progress("Creating a temporary environment")
    made = subprocess.run([sys.executable, "-m", "venv", venv], capture_output=True, text=True)
    if made.returncode != 0:
        print(json.dumps({"console": "Couldn't create the environment:\n" + made.stderr[-1500:], "failed": True}))
        sys.exit()
progress("Installing " + ", ".join(names))
pip = subprocess.Popen([python, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--progress-bar", "off"] + names,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
lines = []
for line in pip.stdout:
    line = line.rstrip()
    lines.append(line)
    if line.startswith(("Collecting", "Downloading", "Installing collected", "Successfully installed")):
        progress(line[:120])
pip.wait()
if pip.returncode != 0:
    tail = "\n".join(lines[-15:])
    offline = any(w in tail for w in ("NewConnectionError", "Network is unreachable", "nodename nor servname", "Temporary failure"))
    why = "It couldn't reach the internet (local-only mode is on, or there's no connection)." if offline else tail
    print(json.dumps({"console": "Couldn't install " + ", ".join(names) + ".\n" + why, "failed": True}))
else:
    print(json.dumps({"console": "Installed " + ", ".join(names) + " in Run Python's environment.", "failed": False}))
