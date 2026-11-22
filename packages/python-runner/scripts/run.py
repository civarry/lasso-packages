#!/usr/bin/env python3
# Runs Python from Lasso's chat. Lasso sends {"command": "block" | "run", "text": ...} on standard input:
# a code block's code (Run), or the text after /run or the last reply (a tool call's "text" argument).
#
# - The code: the ```python blocks in the text (a block whose first line is "# name.py" is saved as that
#   file, so a reply's helper module can be imported), and the last unnamed block (or main.py) runs.
#   No blocks: the whole text is the code.
# - It runs with this Mac's python3, in Lasso's sandbox (no internet, only its own folders), for at
#   most 20 seconds, in a new folder under ~/LassoWorkspace/python-runner/ where it can write files.
# - It answers with what it printed, its error and the files it made. Run also shows a picture it
#   saved (.png, .jpg) or a page it wrote (.html, .svg: a chart from plotly, say) in the code block.
import json, os, pwd, re, subprocess, sys, time

LIMIT = 20
MAX_OUTPUT = 3000

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
        code = re.sub(r"^\s*/run\b", "", text).strip()
        return [(None, code)] if code else []
    return found

def looks_like_words(text):
    """'the code above', 'run it please': words, not Python (no code block, and not valid Python)."""
    if "```" in text:
        return False
    try:
        compile(text, "main.py", "exec")
        return False
    except SyntaxError:
        words = re.findall(r"[A-Za-z']+", text)
        return len(words) >= 2 and not re.search(r"[=():\[\]{}]", text)

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

# A code block's Run button (Lasso 0.28): the console, a picture, and buttons for what to do next.

PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "sklearn": "scikit-learn", "yaml": "pyyaml",
             "bs4": "beautifulsoup4", "dateutil": "python-dateutil", "dotenv": "python-dotenv", "docx": "python-docx",
             "Crypto": "pycryptodome", "skimage": "scikit-image", "attr": "attrs", "magic": "python-magic"}

def environment_python():
    """The package's own environment (made by Install), else this Mac's python3."""
    venv = os.path.join(os.environ.get("HOME", "."), "venv", "bin", "python")
    return venv if os.path.exists(venv) else sys.executable

def progress(line):
    print("progress: " + line, file=sys.stderr, flush=True)

def run_block(data):
    code = data.get("text", "")
    reply = data.get("reply", "")
    folder = run_folder()
    # Files the reply names ("# helper.py" blocks), so this block can import them.
    for name, body in blocks(reply):
        if name and body.strip() != code.strip():
            path = os.path.normpath(os.path.join(folder, name))
            if path.startswith(folder + os.sep):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(body)
    main_file = os.path.join(folder, "main.py")
    with open(main_file, "w", encoding="utf-8") as f:
        f.write(code)
    python = environment_python()
    progress("Initializing environment" if python == sys.executable else "Using the installed packages")
    before = set(os.listdir(folder))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONUNBUFFERED="1")
    progress("Running code")
    try:
        done = subprocess.run([python, "-X", "utf8", main_file], cwd=folder, env=env, stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=LIMIT)
        out, err, status, late = done.stdout, done.stderr, done.returncode, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        status, late = 1, True
    err = err.replace(folder + os.sep, "")
    text = clip(out.rstrip("\n"))
    if err.strip():
        text = (text + "\n" if text else "") + clip(err.rstrip("\n"))
    if late:
        text += f"\nStopped after {LIMIT} s."
    if not text and status == 0:
        text = "(It printed nothing.)"
    made = sorted(f for f in set(os.listdir(folder)) - before if not f.startswith("."))
    if made:
        text += ("\n" if text else "") + "Made " + ", ".join(made[:10]) + " in " + folder.replace(pwd.getpwuid(os.getuid()).pw_dir, "~", 1)
    answer = {"console": text, "failed": status != 0}
    def newest(*kinds):
        found = [os.path.join(folder, f) for f in made if f.lower().endswith(kinds)]
        return max(found, key=os.path.getmtime) if found else None
    page, picture = newest(".html", ".htm", ".svg"), newest(".png", ".jpg", ".jpeg")
    if page:
        answer["html"] = page
    elif picture:
        answer["image"] = picture
    if re.search(r"\b(tkinter|_tkinter|turtle)\b", err):
        answer["console"] += "\nWindows can't open from Lasso's sandbox. To see a drawing, save it as a picture or a page (an .html or .svg file): Run shows it here."
    missing = re.search(r"ModuleNotFoundError: No module named '([\w.]+)'", err)
    if missing:
        module = missing.group(1).split(".")[0]
        name = PIP_NAMES.get(module, module)
        answer["console"] += f"\n{name} isn't installed. Install it in a temporary environment that only Run Python uses?"
        answer["actions"] = [{"title": f"Install {name}", "command": "install", "input": {"packages": name}, "rerun": True}]
    elif status != 0 and not late:
        tail = "\n".join(err.strip().splitlines()[-12:])
        answer["actions"] = [{"title": "Fix it", "chat": (
            "This Python code failed when I ran it:\n\n```python\n" + code.strip() + "\n```\n\n```text\n" + tail +
            "\n```\n\nFix it and give the whole corrected code in one python block.")}]
    print(json.dumps(answer))

def run_folder():
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
    return os.path.realpath(folder)

def main():
    data = json.load(sys.stdin)
    if data.get("command") == "block":
        run_block(data)
        return
    text = data.get("text", "")
    folder = run_folder()
    typed = re.sub(r"^\s*/run\b", "", text).strip()
    if looks_like_words(typed):
        os.rmdir(folder)
        print(json.dumps({"text": f"“{typed}” isn't Python. Type **/run** on its own to run the code in the last reply, or **/run** followed by your code."}))
        return
    path = prepare(text, folder)
    if not path:
        print(json.dumps({"text": "There's no Python to run. Type **/run** after a reply with a Python code block, or **/run** and the code."}))
        return
    before = set(os.listdir(folder))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg", PYTHONUNBUFFERED="1")
    started = time.monotonic()
    try:
        done = subprocess.run([environment_python(), "-X", "utf8", path], cwd=folder, env=env, stdin=subprocess.DEVNULL,
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
                  if f != "main.py" and not f.startswith("."))
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
            lines.append("Windows can't open from Lasso's sandbox. Save a drawing as a picture or a page instead, and use the code block's **Run** to see it.")
    if made:
        place = folder.replace(pwd.getpwuid(os.getuid()).pw_dir, "~", 1)
        lines.append("Made " + ", ".join(f"`{f}`" for f in made[:10]) + f" in `{place}`.")
    print(json.dumps({"text": "\n\n".join(lines)}))

main()
