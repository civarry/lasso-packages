#!/usr/bin/env python3
# Runs Python from Lasso's chat. Lasso sends {"command": "run" | "draw", "text": ...} on standard input:
# the text after /run or /draw, or the last reply (a tool call's "text" argument for the model).
#
# - The code: the ```python blocks in the text (a block whose first line is "# name.py" is saved as that
#   file, so a reply's helper module can be imported), and the last unnamed block (or main.py) runs.
#   No blocks: the whole text is the code.
# - It runs with this Mac's python3, in Lasso's sandbox (no internet, only its own folders), for at
#   most 20 seconds, in a new folder under ~/LassoWorkspace/python-runner/ where it can write files.
# - /run answers with what it printed, its error and the files it made. /draw also gives it a turtle
#   that draws to a picture (Lasso's sandbox can't open windows), and answers with the picture.
import json, os, pwd, re, subprocess, sys, time

LIMIT = 20
MAX_OUTPUT = 3000
HERE = os.path.dirname(os.path.abspath(__file__))

def blocks(text):
    """(name or None, code) for each fenced Python block, or the whole text when there are none."""
    found = []
    for lang, body in re.findall(r"```[ \t]*([A-Za-z0-9_+-]*)[^\n]*\n(.*?)```", text, re.S):
        if lang.lower() not in ("", "python", "py", "python3"):
            continue
        first = body.lstrip().split("\n", 1)[0].strip()
        m = re.match(r"#\s*(?:file:\s*)?([\w./-]+\.py)\s*$", first)
        found.append((m.group(1) if m else None, body))
    if not found:
        code = re.sub(r"^\s*/(run|draw)\b", "", text).strip()
        return [(None, code)] if code else []
    return found

def prepare(text, folder):
    """Writes the blocks into the folder; returns the file to run."""
    parts = blocks(text)
    if not parts:
        return None
    main = None
    for name, code in parts:
        if name:
            path = os.path.normpath(os.path.join(folder, name))
            if not path.startswith(folder + os.sep):
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(code)
            if os.path.basename(name) == "main.py":
                main = path
    unnamed = [code for name, code in parts if not name]
    if unnamed:
        main = os.path.join(folder, "main.py")
        with open(main, "w", encoding="utf-8") as f:
            f.write(unnamed[-1])
    elif main is None:
        main = os.path.normpath(os.path.join(folder, parts[-1][0]))
    return main

def clip(text):
    text = text.rstrip()
    return text if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + f"\n… ({len(text) - MAX_OUTPUT} more characters)"

def fence(text):
    return "```text\n" + text.replace("```", "`​``") + "\n```"

def main():
    data = json.load(sys.stdin)
    drawing = data.get("command") == "draw"
    text = data.get("text", "")
    # ~/LassoWorkspace/python-runner (Lasso makes it; HOME here is the package's own data folder), or
    # the data folder when the workspace isn't there (lasso-pkg).
    root = os.path.join(pwd.getpwuid(os.getuid()).pw_dir, "LassoWorkspace", "python-runner")
    if not os.access(root, os.W_OK):
        root = os.path.join(os.environ.get("HOME", "."), "runs")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    folder, n = os.path.join(root, stamp), 2
    while os.path.exists(folder):
        folder, n = os.path.join(root, f"{stamp}-{n}"), n + 1
    os.makedirs(folder)
    folder = os.path.realpath(folder)
    path = prepare(text, folder)
    if not path:
        print(json.dumps({"text": "There's no Python to run. Type **/run** after a reply with a Python code block, or **/run** and the code."}))
        return
    before = set(os.listdir(folder))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONUNBUFFERED="1")
    if drawing:
        env["PYTHONPATH"] = os.path.join(HERE, "headless")
        env["LASSO_DRAWING"] = os.path.join(folder, "drawing")
    started = time.monotonic()
    try:
        done = subprocess.run([sys.executable, "-X", "utf8", path], cwd=folder, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=LIMIT)
        out, err, code, late = done.stdout, done.stderr, done.returncode, False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        code, late = None, True
    seconds = time.monotonic() - started
    # Tracebacks name the file, not the run folder's long path.
    err = err.replace(folder + os.sep, "")
    made = sorted(f for f in set(os.listdir(folder)) - before
                  if f not in ("main.py", "drawing.pdf") and not f.startswith("."))
    if drawing:
        picture = os.path.join(folder, "drawing.png")
        images = [os.path.join(folder, f) for f in made if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if os.path.exists(picture) or images:
            print(json.dumps({"path": picture if os.path.exists(picture) else max(images, key=os.path.getmtime)}))
            return
        why = clip(err) if err.strip() else "It didn't draw anything with turtle or save a picture."
        print(json.dumps({"text": "Nothing to show.\n\n" + fence(why)}))
        return
    version = "Python " + sys.version.split()[0]
    head = f"**Ran {os.path.basename(path)}** · {version} · {seconds:.2f} s"
    lines = [head]
    if late:
        lines[0] += f" · stopped after {LIMIT} s"
    if out.strip():
        lines.append(fence(clip(out)))
    elif not err.strip() and not late:
        lines.append("It printed nothing.")
    if err.strip():
        lines.append("**Error**" if code else "**Messages**")
        lines.append(fence(clip(err)))
        if "EOFError" in err:
            lines.append("It asked for input, which chat can't type in yet: put the values in the code instead.")
        if re.search(r"\b(tkinter|_tkinter|turtle)\b", err):
            lines.append("Windows can't open from Lasso's sandbox. For turtle drawings, use **/draw**: it shows the picture.")
    if made:
        place = folder.replace(pwd.getpwuid(os.getuid()).pw_dir, "~", 1)
        lines.append("Made " + ", ".join(f"`{f}`" for f in made[:10]) + f" in `{place}`.")
    print(json.dumps({"text": "\n\n".join(lines)}))

main()
