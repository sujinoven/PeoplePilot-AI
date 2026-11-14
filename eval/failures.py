import json
import sys
from collections import defaultdict

run = json.load(open(sys.argv[1], encoding="utf-8"))
fails = defaultdict(lambda: defaultdict(int))
for rec in run["cases"]:
    for metric, s in rec["scores"].items():
        if s["score"] is not None and s["score"] < 1:
            fails[rec["id"]][metric] += 1
for cid in sorted(fails):
    print(cid, dict(fails[cid]))