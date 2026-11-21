#!/usr/bin/env python3
# Searches the notes folder the user chose for the words of their question. Lasso gives it read access
# to that folder only, sends {"query": ...} on standard input, and reads {"results": [...]} back.
# A note counts when it holds at least 2 of the words (the only one, for a one-word question); its
# passage is the lines that hold the most of them.
import json, os, re, sys

def stem(word):
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    return word[:-1] if len(word) > 4 and word.endswith("e") else word

data = json.load(sys.stdin)
folder = data["settings"].get("notes", "")
words = []
for w in re.findall(r"\w+", data.get("query", "").lower()):
    if len(w) > 2 and stem(w) not in words:
        words.append(stem(w))
need = min(2, len(words))
hits = []
if folder and words:
    for root, _, names in os.walk(folder):
        for name in names:
            if not name.lower().endswith((".md", ".txt", ".markdown")):
                continue
            path = os.path.join(root, name)
            try:
                text = open(path, encoding="utf-8", errors="ignore").read(200_000)
            except OSError:
                continue
            present = {stem(w) for w in re.findall(r"\w+", text.lower())}
            found = [w for w in words if w in present]
            if len(found) < need:
                continue
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            scored = sorted(lines, key=lambda l: -sum(stem(w) in found for w in re.findall(r"\w+", l.lower())))
            snippet = " ".join(" ".join(scored[:3]).split())[:400]
            hits.append((len(found), name, path, snippet))
hits.sort(key=lambda h: (-h[0], h[1]))
print(json.dumps({"results": [
    {"title": os.path.splitext(n)[0], "url": "file://" + p, "snippet": s} for _, n, p, s in hits[:10]
]}))
