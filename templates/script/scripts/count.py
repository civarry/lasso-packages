#!/usr/bin/env python3
# Lasso writes one JSON object to standard input and reads the answer from standard output.
import json, sys
data = json.load(sys.stdin)
words = len(data["text"].split())
print(json.dumps({"text": f"**{words}** words"}))
