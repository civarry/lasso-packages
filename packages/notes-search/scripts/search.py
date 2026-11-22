#!/usr/bin/env python3
# Searches the notes folder the user chose for the words of their question. Lasso gives it read access
# to that folder only and a writable folder of its own (HOME), sends {"query": ...} on standard input,
# and reads {"results": [...]} back.
#
# The index: HOME keeps, per note, its size, date, title and word counts. Each search only looks at the
# dates of the files, reads the notes that changed since last time, and drops the ones that are gone, so
# a large folder is read once, not on every question. A first run on a huge folder indexes what it can
# in its time budget and carries on next time.
#
# Ranking: BM25 over light stems (the same stems Lasso's gate uses), with a note's title and headings
# counting more, notes holding more of the question's words first, and newer notes winning ties. A note
# counts when it holds at least 2 of the words (the only one, for a one-word question). Its passage is
# the paragraph (or list block) that holds the most of them, with the heading it sits under.
import json, math, os, pickle, re, sys, time

START = time.monotonic()
BUDGET = 2.5                      # seconds for reading changed notes; Lasso stops the search at 5
MAX_READ = 200_000                # characters read from one note
EXTENSIONS = (".md", ".markdown", ".txt")
SKIP_DIRS = {"node_modules", ".git", ".obsidian", ".trash", ".Trash", "__pycache__"}
INDEX_VERSION = 2
WORD = re.compile(r"\w+")

def stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    return word[:-1] if len(word) > 4 and word.endswith("e") else word

def stems(text):
    return [stem(w) for w in WORD.findall(text.lower()) if len(w) > 2]

def split_front_matter(text):
    """(front matter title or "", the text without its YAML front matter)."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    head = text[3:end]
    title = ""
    for line in head.splitlines():
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip().strip("\"'")
    return title, text[end + 4:]

def heading(line):
    s = line.strip()
    return s.lstrip("#").strip() if s.startswith("#") and s.lstrip("#").startswith(" ") else None

def read(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read(MAX_READ)

def index_note(path, name):
    text = read(path)
    title, body = split_front_matter(text)
    headings = [h for h in (heading(l) for l in body.splitlines()) if h]
    title = title or (headings[0] if headings else os.path.splitext(name)[0])
    counts = {}
    for s in stems(body):
        counts[s] = counts.get(s, 0) + 1
    strong = set(stems(title + " " + os.path.splitext(name)[0] + " " + " ".join(headings)))
    return {"title": title, "len": sum(counts.values()), "tf": counts, "strong": strong}

def load_index(home, folder):
    try:
        with open(os.path.join(home, "index.pickle"), "rb") as f:
            index = pickle.load(f)
        if index.get("version") == INDEX_VERSION and index.get("folder") == folder:
            return index
    except Exception:
        pass
    return {"version": INDEX_VERSION, "folder": folder, "notes": {}}

def save_index(home, index):
    tmp = os.path.join(home, "index.pickle.tmp")
    try:
        with open(tmp, "wb") as f:
            pickle.dump(index, f, protocol=4)
        os.replace(tmp, os.path.join(home, "index.pickle"))
    except OSError:
        pass

def refresh(index, folder):
    """Brings the index up to date with the folder, within the time budget."""
    notes = index["notes"]
    seen, changed = set(), False
    pending = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS]
        for name in names:
            if name.startswith(".") or not name.lower().endswith(EXTENSIONS):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            rel = os.path.relpath(path, folder)
            seen.add(rel)
            old = notes.get(rel)
            if old is None or old["mtime"] != st.st_mtime or old["size"] != st.st_size:
                pending.append((st.st_mtime, rel, path, name, st))
    # Newest first, so a first run on a big folder has the recent notes.
    pending.sort(reverse=True)
    for _, rel, path, name, st in pending:
        if time.monotonic() - START > BUDGET:
            break
        try:
            note = index_note(path, name)
        except OSError:
            continue
        note.update(mtime=st.st_mtime, size=st.st_size)
        notes[rel] = note
        changed = True
    for rel in [r for r in notes if r not in seen]:
        del notes[rel]
        changed = True
    return changed

def rank(index, words):
    notes = index["notes"]
    total = len(notes)
    if not total:
        return []
    average = sum(n["len"] for n in notes.values()) / total or 1
    df = {w: sum(1 for n in notes.values() if w in n["tf"] or w in n["strong"]) for w in words}
    need = min(2, len(words))
    scored = []
    for rel, note in notes.items():
        found = [w for w in words if w in note["tf"] or w in note["strong"]]
        if len(found) < need:
            continue
        score = 0.0
        for w in found:
            idf = math.log(1 + (total - df[w] + 0.5) / (df[w] + 0.5))
            tf = note["tf"].get(w, 0)
            score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * note["len"] / average)) if tf else 0
            if w in note["strong"]:
                score += idf * 1.5
        scored.append((len(found), score, note["mtime"], rel, note, found))
    scored.sort(key=lambda s: (-s[0], -s[1], -s[2]))
    return scored

def passage(text, found, title="", limit=380):
    """The block that holds the most of the words, with the heading it's under. A word already in the
    note's title doesn't need to be in the passage too (the title goes with it)."""
    _, body = split_front_matter(text)
    blocks, current, under = [], [], ""
    for line in body.splitlines() + [""]:
        h = heading(line)
        if h is not None or not line.strip():
            if current:
                blocks.append((under, " ".join(current)))
                current = []
            if h is not None:
                under = h
            continue
        item = line.strip()
        bullet = item[:2] in ("- ", "* ", "+ ") or re.match(r"\d+[.)] ", item)
        item = re.sub(r"^([-*+>]|\d+[.)])\s+", "", item)
        if current and bullet:
            current[-1] = current[-1].rstrip(";,.") + ";"
        current.append(item)
    want = set(found) - set(stems(title)) or set(found)
    def score(block):
        present = stems(block[0] + " " + block[1])
        return (len(want & set(present)), sum(p in want for p in present))
    if not blocks:
        return ""
    best = max(blocks, key=score)
    text = " ".join(best[1].split())
    # Start near the first matching word when the block is long.
    if len(text) > limit:
        first = min((m.start() for m in WORD.finditer(text.lower()) if stem(m.group()) in want), default=0)
        cut = text.rfind(". ", 0, first)
        start = cut + 2 if cut >= 0 and first - cut < limit // 2 else max(0, first - 60)
        text = ("… " if start else "") + text[start:start + limit].rstrip() + "…"
    # The block alone may miss a word the note has elsewhere: add the next best block's sentence.
    if len(want & set(stems(best[0] + " " + text))) < min(2, len(want)):
        others = sorted((b for b in blocks if b is not best), key=score, reverse=True)
        if others:
            text = (text + " … " + " ".join(others[0][1].split()))[: limit + 80]
    return (best[0] + ": " if best[0] else "") + text

def main():
    data = json.load(sys.stdin)
    folder = data.get("settings", {}).get("notes", "")
    words = []
    for s in stems(data.get("query", "")):
        if s not in words:
            words.append(s)
    if not folder or not os.path.isdir(folder) or not words:
        print(json.dumps({"results": []}))
        return
    folder = os.path.realpath(folder)
    home = os.environ.get("HOME") or os.getcwd()
    index = load_index(home, folder)
    if refresh(index, folder):
        save_index(home, index)
    results = []
    for _, _, mtime, rel, note, found in rank(index, words)[:5]:
        try:
            snippet = passage(read(os.path.join(folder, rel)), found, note["title"])
        except OSError:
            continue
        name = os.path.splitext(rel)[0]
        title = note["title"] if note["title"].lower() == os.path.basename(name).lower() else f"{note['title']} ({name})"
        edited = time.strftime("%Y-%m-%d", time.localtime(mtime))
        results.append({"title": title, "url": "file://" + os.path.join(folder, rel),
                        "snippet": f"[edited {edited}] {snippet}"})
    print(json.dumps({"results": results}))

main()
