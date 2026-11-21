#!/usr/bin/env python3
# Searches the notes folder the user chose for the words in the query. Lasso gives it read access to
# that folder only, and reads {"results": [...]} back.
import json, os, re, sys

data = json.load(sys.stdin)
folder = data["settings"].get("notes", "")
words = [w for w in re.findall(r"\w+", data.get("query", "").lower()) if len(w) > 2]
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
            lower = text.lower()
            score = sum(lower.count(w) for w in words)
            if score:
                at = min((lower.find(w) for w in words if w in lower), default=0)
                snippet = " ".join(text[max(0, at - 120): at + 280].split())
                hits.append((score, name, path, snippet))
hits.sort(reverse=True)
print(json.dumps({"results": [
    {"title": os.path.splitext(n)[0], "url": "file://" + p, "snippet": s} for _, n, p, s in hits[:10]
]}))
