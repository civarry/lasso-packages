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
import datetime, json, math, os, pickle, re, sys, time

START = time.monotonic()
BUDGET = 2.5                      # seconds for reading changed notes; Lasso stops the search at 5
MAX_READ = 200_000                # characters read from one note
EXTENSIONS = (".md", ".markdown", ".txt")
SKIP_DIRS = {"node_modules", ".git", ".obsidian", ".trash", ".Trash", "__pycache__"}
INDEX_VERSION = 6
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
    return {"title": title, "len": sum(counts.values()), "tf": counts, "strong": strong, "named": named,
            "date": note_date(rel or name, text, title)}

MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

def note_date(rel, text, title):
    """The day a note is about: a date in its file name, its front matter's date:, or its title
    ("Weekly sync, 14 Nov 2026"). None means: use the day it was last edited."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", rel)
    if not m:
        m = re.search(r"^date:\s*(\d{4})-(\d{2})-(\d{2})", text[:2000], re.M)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?,?\s+(\d{4})\b", title) or None
    if m and m.group(2).lower() in MONTHS:
        try:
            return datetime.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"\b([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b", title)
    if m and m.group(1).lower() in MONTHS:
        try:
            return datetime.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
        except ValueError:
            return None
    return None

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

def rank(index, words, need=None, only=None):
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
    need = min(2, len(words)) if need is None else need
    scored = []
    for rel, note in notes.items():
        if only is not None and rel not in only:
            continue
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

def listing(index, folder):
    """'What's in my notes': folders with how many notes each, loose notes, the newest few."""
    notes = index["notes"]
    folders, top = {}, []
    for rel in notes:
        parts = rel.split(os.sep)
        if len(parts) == 1:
            top.append(rel)
        else:
            folders.setdefault(parts[0], []).append(os.sep.join(parts[1:]))
    lines = [f"{len(notes)} notes in {folder.replace(os.path.expanduser('~'), '~', 1)}."]
    if folders:
        described = []
        for name, inside in sorted(folders.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:12]:
            subs = {}
            for r in inside:
                if os.sep in r:
                    subs[r.split(os.sep)[0]] = subs.get(r.split(os.sep)[0], 0) + 1
            if subs:
                detail = ": " + ", ".join(f"{k}/ {v}" for k, v in sorted(subs.items(), key=lambda kv: -kv[1])[:6])
            else:
                detail = ": " + ", ".join(sorted(inside)) if len(inside) <= 4 else ""
            described.append(f"{name}/ ({len(inside)} note{'s' if len(inside) != 1 else ''}{detail})")
        lines.append("Folders: " + "; ".join(described) + ".")
    if top:
        lines.append("Not in a folder: " + ", ".join(sorted(top)[:25]) + ".")
    newest = sorted(notes, key=lambda r: -notes[r]["mtime"])[:8]
    lines.append("Most recently changed: " + ", ".join(newest) + ".")
    return "\n".join(lines)

COMMON = set("""the and for are but not you your all any can had was one our out has have how its new now old see two
way who did does get got let say use used that this these those with from they them then than there their what when
where which while will would could should about into over also just like some such very more most much many only
other here were been each every both few own same why yes please find give look make made take need want help using
part parts index introduction contents notes note file files page pages""".split())

def describe(index):
    """describe/1: the What's in it line (folder and loose note names first, then the words note
    titles share) and picking words, whole words, never stems."""
    notes = index["notes"]
    def words_of(text):
        return [w for w in re.findall(r"[^\W_]+", text.lower().replace("-", " ")) if len(w) > 2 and not w.isdigit() and w not in COMMON]
    leading = []
    for rel in sorted(notes):
        first = rel.split(os.sep)[0]
        for w in words_of(first if os.sep in rel else os.path.splitext(first)[0]):
            if w not in leading:
                leading.append(w)
    # Picking words from every folder in turn, so a big docs folder doesn't crowd out a few personal
    # notes ("kestrel", "adobo" beside 550 Python pages).
    groups = {}
    for rel, note in notes.items():
        group = rel.split(os.sep)[0] if os.sep in rel else ""
        counts = groups.setdefault(group, {})
        for w in set(words_of(note["title"]) + words_of(os.path.splitext(os.path.basename(rel))[0])):
            counts[w] = counts.get(w, 0) + 1
    ranked = [[w for w, c in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])) if c <= max(1, len(notes) * 0.5)]
              for _, c in sorted(groups.items(), key=lambda kv: len(kv[1]))]
    words = [w for w in leading]
    while len(words) < 100 and any(ranked):
        for r in ranked:
            while r and r[0] in words:
                r.pop(0)
            if r:
                words.append(r.pop(0))
    words = words[:100]
    about = ""
    for w in leading + [w for w in words if w not in leading]:
        nxt = w if not about else about + ", " + w
        if len(nxt) > 120:
            break
        about = nxt
    return about, words

def open_index(folder):
    folder = os.path.realpath(folder)
    home = os.environ.get("HOME") or os.getcwd()
    index = load_index(home, folder)
    if refresh(index, folder):
        save_index(home, index)
    return folder, index

def main():
    data = json.load(sys.stdin)
    folder = data.get("settings", {}).get("notes", "")
    hook = data.get("hook")
    if not folder or not os.path.isdir(folder):
        print(json.dumps({"about": "", "words": []} if hook == "describe/1" else {"status": "nothing", "results": []}))
        return
    folder, index = open_index(folder)
    if hook == "describe/1":
        about, words = describe(index)
        print(json.dumps({"about": about, "words": words}))
        return
    if data.get("intent") == "about":
        print(json.dumps({"status": "inventory", "results": [
            {"title": "Files in My notes", "url": "file://" + folder, "snippet": listing(index, folder)}]}))
        return
    chosen = data.get("searchFor")
    previous = (data.get("previous") or {}).get("message") if isinstance(data.get("previous"), dict) else None
    followed = bool(data.get("previousSearched"))
    today = parse_day(data.get("today")) or datetime.date.today()
    message = data.get("message") or data.get("query", "")
    span, label = (None, None) if chosen else date_span(message, today)
    text = chosen or data.get("query", "")
    words = [w for w in dict.fromkeys(stems(text)) if w not in FILIPINO and w not in DATE_WORDS]
    vocab = vocabulary(index)
    searched = None
    if not chosen:
        # A word no note has: the closest word that some note has, when it's clearly a typo.
        fixed, ask = [], None
        for w in words:
            if w in vocab:
                fixed.append(w)
                continue
            near = closest(w, vocab) if len(w) >= 5 else None
            if near and near[1] <= (1 if len(w) < 9 else 2) and near[2] > near[1]:
                fixed.append(near[0])
            else:
                fixed.append(w)
                if near and ask is None and len(w) >= 6:
                    ask = near[0]
        if fixed != words:
            searched = " ".join(surface(index, folder, f) if f not in words else original(text, f) for f in fixed)
            words = fixed
    else:
        ask = None
    # A follow-up ("show me an example") after a turn that used these notes: the previous question's
    # words too, so it finds the same subject.
    total = len(index["notes"]) or 1
    def rare(w):
        return sum(1 for n in index["notes"].values() if w in n["tf"] or w in n["strong"]) <= max(5, total * 0.02)
    # Only when its own words say nothing specific ("show me an example", "more about that").
    if (not chosen and not span and followed and previous
            and len([w for w in words if w in vocab]) <= 2 and not any(rare(w) for w in words if w in vocab)
            # A word no note has ("wifi") is a new subject, not a follow-up.
            and all(w in vocab for w in words)):
        before = [w for w in dict.fromkeys(stems(previous)) if w not in FILIPINO and w not in DATE_WORDS and w in vocab
                  and w not in STOP]
        words = list(dict.fromkeys(before + words))
        if searched is None:
            searched = " ".join(original(previous + " " + text, w) for w in words)
    known = [w for w in words if w in vocab]
    only = None
    if span:
        only = {rel for rel, n in index["notes"].items() if span[0] <= note_day(n) <= span[1]}
    # Words no note has (another language, a typo it couldn't fix) can't be matched, so they don't count
    # toward the 2-word rule; a single remaining word must then be rare, so "wifi password" doesn't
    # match every page that mentions a password.
    need = min(2, len(known))
    if span and known:
        need = 1
    elif len(known) == 1 and len(words) > 1:
        df = sum(1 for n in index["notes"].values() if known[0] in n["tf"] or known[0] in n["strong"])
        if df > max(5, total * 0.01):
            known = []
    results = []
    if known or (span and not words):
        scored, idf = rank(index, known, need=need, only=only) if known else (
            [(0, n["mtime"], rel, n, []) for rel, n in index["notes"].items() if rel in only], {})
        picked = select(scored, idf) if known else sorted(scored, key=lambda s: -s[1])[:5]
        for _, mtime, rel, note, found in picked:
            try:
                snippet = passage(read(os.path.join(folder, rel)), found, note["title"]) if found else first_lines(read(os.path.join(folder, rel)))
            except OSError:
                continue
            name = os.path.splitext(rel)[0]
            title = note["title"] if note["title"].lower() == os.path.basename(name).lower() else f"{note['title']} ({name})"
            results.append({"title": title, "url": "file://" + os.path.join(folder, rel),
                            "date": note.get("date") or time.strftime("%Y-%m-%d", time.localtime(mtime)), "snippet": snippet})
    out = {"status": "found" if results else "nothing", "results": results}
    if not results and followed and not chosen and not span:
        out["status"] = "irrelevant"
    if searched:
        out["searched"] = searched
    if ask and not results:
        out["ask"] = ask
    if span:
        out["note"] = (f"Only notes dated {label} ({span[0].strftime('%d %b')} to {span[1].strftime('%d %b %Y')})."
                       if results else f"No notes dated {label} ({span[0].strftime('%d %b')} to {span[1].strftime('%d %b %Y')}).")
    print(json.dumps(out))

STOP = set("""what when where which who how why the and for are but not you your all any can had was one our out has
have this that these those with from they them then than there their about into over also just like some such very more
most much many only other here were been show tell give find look explain example examples""".split())
FILIPINO = set("""paano ano ang ng mga sa na ba ko mo ito iyan yan yung iyong po naman lang saan kailan bakit sino
magkano para may wala din rin pa at o kung kasi kay kina nila natin namin ninyo siya sila tayo kami kayo ako ikaw
dito doon diyan ganito ganyan pwede puwede gusto alam meron mayroon""".split())
DATE_WORDS = {"today", "yesterday", "week", "last", "this", "month", "year", "ago", "day", "days"}

def parse_day(text):
    try:
        return datetime.date.fromisoformat(text)
    except (TypeError, ValueError):
        return None

def date_span(message, today):
    """'last week', 'this week', 'yesterday', 'today', 'last month', 'this month', 'last N days':
    the days it means, and how to say it."""
    m = message.lower()
    monday = today - datetime.timedelta(days=today.weekday())
    if re.search(r"\blast week\b|\bprevious week\b", m):
        start = monday - datetime.timedelta(days=7)
        return (start, start + datetime.timedelta(days=6)), "last week"
    if re.search(r"\bthis week\b", m):
        return (monday, today), "this week"
    if re.search(r"\byesterday\b", m):
        d = today - datetime.timedelta(days=1)
        return (d, d), "yesterday"
    if re.search(r"\btoday\b", m):
        return (today, today), "today"
    first = today.replace(day=1)
    if re.search(r"\blast month\b", m):
        end = first - datetime.timedelta(days=1)
        return (end.replace(day=1), end), "last month"
    if re.search(r"\bthis month\b", m):
        return (first, today), "this month"
    n = re.search(r"\blast (\d{1,3}) days\b", m)
    if n:
        return (today - datetime.timedelta(days=int(n.group(1))), today), f"in the last {n.group(1)} days"
    return None, None

def note_day(note):
    return parse_day(note.get("date")) or datetime.date.fromtimestamp(note["mtime"])

def vocabulary(index):
    vocab = index.get("_vocab")
    if vocab is None:
        vocab = set()
        for n in index["notes"].values():
            vocab.update(n["tf"])
            vocab.update(n["strong"])
        index["_vocab"] = vocab
    return vocab

def distance(a, b, limit):
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb),
                           prev[j - 2] + 1 if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb else limit + 9))
        prev = cur
    return prev[-1]

def closest(word, vocab):
    """The nearest word some note has: (word, distance, next best distance)."""
    if len(word) < 4:
        return None
    best = []
    for v in vocab:
        if v[0] != word[0] or abs(len(v) - len(word)) > 2:
            continue
        d = distance(word, v, 2)
        if d <= 2:
            best.append((d, v))
    if not best:
        return None
    best.sort()
    return (best[0][1], best[0][0], best[1][0] if len(best) > 1 else 99)

def original(text, stemmed):
    for w in re.findall(r"[^\W_]+", text.lower()):
        if stem(w) == stemmed:
            return w
    return stemmed

def surface(index, folder, stemmed):
    """How a corrected word is written in the notes ("frozendict", not a stem)."""
    for rel, n in index["notes"].items():
        if stemmed in n["strong"] or stemmed in n["tf"]:
            try:
                return original(read(os.path.join(folder, rel)), stemmed)
            except OSError:
                break
    return stemmed

def first_lines(text, limit=380):
    _, body = split_front_matter(text)
    return " ".join(" ".join(l.strip().lstrip("#-*> ") for l in body.splitlines() if l.strip()).split())[:limit]

main()
