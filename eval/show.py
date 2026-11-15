import json
import sys

run = json.load(open(sys.argv[1], encoding="utf-8"))
wanted = sys.argv[2].split(",")
seen = set()
for rec in run["cases"]:
    if rec["id"] in wanted and rec["id"] not in seen:
        seen.add(rec["id"])
        print(f'--- {rec["id"]}  route={rec["route"]}  retrieved={rec["retrieved_pages"]}')
        print("Q:", rec["question"])
        print("A:", rec["answer"])
        for metric, s in rec["scores"].items():
            if s["score"] is not None and s["score"] < 1:
                print("   FAIL", metric, s)
        print()