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
INDEX_VERSION = 5
WORD = re.compile(r"\w+")

def stem_once(word):
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    return word[:-1] if len(word) > 4 and word.endswith("e") else word

def stem(word):
    """Lasso's light stem, applied until nothing changes, so "meetings" and "meeting" both give "meet"."""
    for _ in range(3):
        shorter = stem_once(word)
        if shorter == word:
            break
        word = shorter
    return word

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

def index_note(path, name, rel=""):
    text = read(path)
    title, body = split_front_matter(text)
    headings = [h for h in (heading(l) for l in body.splitlines()) if h]
    title = title or (headings[0] if headings else os.path.splitext(name)[0])
    counts = {}
    for s in stems(body):
        counts[s] = counts.get(s, 0) + 1
    # The title, file name, folder names ("meetings/") and headings say what a note is about.
    strong = set(stems(" ".join([title, os.path.splitext(rel or name)[0].replace(os.sep, " ")] + headings)))
    named = set(stems(" ".join([title, os.path.splitext(rel or name)[0].replace(os.sep, " ")])))
    return {"title": title, "len": sum(counts.values()), "tf": counts, "strong": strong, "named": named}

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
            note = index_note(path, name, rel)
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
    """Notes by BM25, scaled by how much of the question's weight they cover, so a rare word
    ("kestrel", "adobo", "csv") counts for more than common ones ("python", "file")."""
    notes = index["notes"]
    total = len(notes)
    if not total:
        return [], {}
    average = sum(n["len"] for n in notes.values()) / total or 1
    df = {w: sum(1 for n in notes.values() if w in n["tf"] or w in n["strong"]) for w in words}
    idf = {w: math.log(1 + (total - df[w] + 0.5) / (df[w] + 0.5)) for w in words}
    weight = sum(idf.values()) or 1
    need = min(2, len(words))
    scored = []
    for rel, note in notes.items():
        found = [w for w in words if w in note["tf"] or w in note["strong"]]
        if len(found) < need:
            continue
        score = 0.0
        for w in found:
            tf = note["tf"].get(w, 0)
            if tf:
                score += idf[w] * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * note["len"] / average))
            if w in note["named"]:
                score += idf[w] * 4.0      # the note is about it: its title, file or folder name
            elif w in note["strong"]:
                score += idf[w] * 1.5      # a heading in it
        coverage = sum(idf[w] for w in found) / weight
        scored.append((score * (0.25 + coverage), note["mtime"], rel, note, found))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    return scored, idf

def select(scored, idf, count=5):
    """The best note, then notes that cover the question's words the ones before didn't: "Kestrel's
    Python version and lazy imports" gets the Kestrel note and the lazy imports page, not three pages
    about lazy imports."""
    pool, picked, covered = scored[:40], [], set()
    weight = sum(idf.values()) or 1
    while pool and len(picked) < count:
        def value(s):
            new = sum(idf[w] for w in s[4] if w not in covered) / weight
            return s[0] * (0.5 + new)
        best = max(pool, key=value)
        pool.remove(best)
        picked.append(best)
        covered.update(best[4])
    return picked

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
    scored, idf = rank(index, words)
    for _, mtime, rel, note, found in select(scored, idf):
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
