#!/usr/bin/env python3
"""The catalog's checks beyond `lasso-pkg validate --catalog`: a changed package's version went up, and
each script command with a `test` and no key or folder runs. Usage: check.py <lasso-pkg> [base-commit]"""
import json, subprocess, sys, tempfile
from pathlib import Path

pkg = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else None
failed = False

def version(text):
    return tuple(int(p) for p in json.loads(text)["version"].split("."))

for folder in sorted(Path("packages").iterdir()):
    manifest = folder / "lasso.json"
    if not manifest.exists():
        continue
    data = json.loads(manifest.read_text())
    if base:
        changed = subprocess.run(["git", "diff", "--quiet", base, "HEAD", "--", str(folder)]).returncode != 0
        old = subprocess.run(["git", "show", f"{base}:{manifest}"], capture_output=True, text=True)
        if changed and old.returncode == 0 and version(manifest.read_text()) <= version(old.stdout):
            print(f"✗ {folder.name}: changed, so its version must go up (it's {data['version']}).")
            failed = True
    needs_setup = any(s.get("kind") in ("secret", "folder") for s in data.get("settings", []))
    for command in data.get("commands", []):
        if "script" in command.get("run", {}) and "test" in command and not needs_setup:
            result = subprocess.run([pkg, "run", str(folder.resolve()), command["id"]], capture_output=True, text=True,
                                    cwd=tempfile.mkdtemp())
            if result.returncode != 0:
                print(f"✗ {folder.name} {command['id']}: its test failed:\n{result.stderr}")
                failed = True
            else:
                print(f"✓ {folder.name} {command['id']}: test ran")
sys.exit(1 if failed else 0)
