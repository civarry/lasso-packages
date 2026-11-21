#!/usr/bin/env python3
import csv, json, os, re, sys
data = json.load(sys.stdin)
rows = [re.split(r"\t|\s{2,}", line.strip()) for line in data["text"].splitlines() if line.strip()]
path = os.path.join(os.environ["TMPDIR"], "table.csv")
with open(path, "w", newline="") as f:
    csv.writer(f).writerows(rows)
print(json.dumps({"path": path}))
