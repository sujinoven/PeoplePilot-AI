"""Compare two evaluation runs.

    uv run python -m eval.compare eval/results/<before>.json eval/results/<after>.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from eval.evaluators import METRICS
from eval.run_eval import HEADLINE


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _scores(run: dict) -> dict[tuple[str, str], float]:
    """(case id, metric) -> mean score over repeats, skipping 'not applicable'."""
    acc: dict[tuple[str, str], list[float]] = defaultdict(list)
    for rec in run["cases"]:
        for metric, s in rec["scores"].items():
            if s["score"] is not None:
                acc[(rec["id"], metric)].append(s["score"])
    return {k: sum(v) / len(v) for k, v in acc.items()}


def compare(before: dict, after: dict) -> str:
    lines = [f"before: {before['label']} ({before['timestamp']})   after: {after['label']} ({after['timestamp']})", ""]
    lines.append(f"{'metric':<18}{'before':>9}{'after':>9}{'change':>10}")
    lines.append("-" * 46)
    for m in METRICS:
        b = before["summary"]["overall"].get(m)
        a = after["summary"]["overall"].get(m)
        if not b or not a or b["rate"] is None or a["rate"] is None:
            continue
        delta = (a["rate"] - b["rate"]) * 100
        lines.append(f"{m:<18}{b['rate'] * 100:>8.1f}%{a['rate'] * 100:>8.1f}%{delta:>+9.1f}")
    # Per split, so a gain on the cases you tuned on can't hide a flat result on held-out cases.
    bs = before["summary"].get("by_split") or {"core": before["summary"]["overall"]}
    as_ = after["summary"].get("by_split") or {"core": after["summary"]["overall"]}
    for split in sorted(set(bs) & set(as_)):
        lines.append("")
        lines.append(f"[{split}]")
        for m in HEADLINE:
            b, a = bs[split].get(m), as_[split].get(m)
            if not b or not a or b["rate"] is None or a["rate"] is None:
                continue
            lines.append(
                f"  {m:<16}{b['passed']:>3}/{b['n']:<3} -> {a['passed']:>3}/{a['n']:<3}"
                f"  ({b['rate'] * 100:.1f}% -> {a['rate'] * 100:.1f}%)"
            )
    bl, al = before["summary"]["latency_s"], after["summary"]["latency_s"]
    lines.append("")
    lines.append("-" * 46)
    lines.append(f"latency p50: {bl['p50']}s -> {al['p50']}s   p95: {bl['p95']}s -> {al['p95']}s")

    sb, sa = _scores(before), _scores(after)
    fixed = sorted(k for k in sa if k in sb and sb[k] < sa[k])
    broke = sorted(k for k in sa if k in sb and sb[k] > sa[k])
    lines.append("")
    lines.append(f"Fixed ({len(fixed)}): " + (", ".join(f"{c}/{m}" for c, m in fixed) or "none"))
    lines.append(f"Regressed ({len(broke)}): " + (", ".join(f"{c}/{m}" for c, m in broke) or "none"))
    if before.get("config") != after.get("config"):
        lines.append("")
        lines.append("Config changed:")
        for key in sorted(set(before.get("config", {})) | set(after.get("config", {}))):
            b, a = before.get("config", {}).get(key), after.get("config", {}).get(key)
            if b != a:
                lines.append(f"  {key}: {b} -> {a}")
    return "\n".join(lines)


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        raise SystemExit("usage: python -m eval.compare BEFORE.json AFTER.json")
    print(compare(_load(argv[0]), _load(argv[1])))


if __name__ == "__main__":
    main()
