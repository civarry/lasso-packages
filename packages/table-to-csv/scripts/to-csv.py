#!/usr/bin/env python3
# Lasso sees the rows and columns of a table you lasso and sends them as "table": one row per line,
# cells separated by tabs. This writes them as a CSV file; Lasso copies it to ~/LassoWorkspace.
import csv, json, os, sys
data = json.load(sys.stdin)
rows = [line.split("\t") for line in data.get("table", "").splitlines() if line.strip()]
if not rows:
    print("No table in this selection.", file=sys.stderr)
    sys.exit(1)
path = os.path.join(os.environ["TMPDIR"], "table.csv")
with open(path, "w", newline="") as f:
    csv.writer(f).writerows(rows)
print(json.dumps({"path": path}))
