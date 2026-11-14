"""Run the PeoplePilot evaluation.

    uv run python -m eval.run_eval --label baseline
    uv run python -m eval.run_eval --label baseline --no-judge        # free: skips the 2 LLM-judge metrics
    uv run python -m eval.run_eval --label try --ids A04,A07 --limit 5  # a quick subset

Each run writes eval/results/<timestamp>_<label>.json. Compare two runs with:

    uv run python -m eval.compare eval/results/<before>.json eval/results/<after>.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from eval.evaluators import METRICS, CaseResult, evaluate_case, result_from_state, retrieved_pages

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "eval" / "dataset.jsonl"
RESULTS_DIR = ROOT / "eval" / "results"

# The numbers that go on a resume, in the order to quote them.
HEADLINE = ["routing", "tool_choice", "tool_args", "retrieval_hit", "citation", "answer_correct", "faithful"]


def load_cases(path: Path = DATASET) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --------------------------------------------------------------------------- running
def run_cases(cases, invoke, judge=None, workers: int = 1, repeats: int = 1) -> list[dict]:
    """Run every case through `invoke(case) -> CaseResult` and score it. Order is preserved."""
    jobs = [(case, r) for case in cases for r in range(repeats)]

    def one(job):
        case, repeat = job
        start = time.perf_counter()
        try:
            res = invoke(case)
        except Exception as exc:  # one bad case must not kill a 60-case run
            res = CaseResult(error=f"{type(exc).__name__}: {exc}")
        latency = time.perf_counter() - start
        scores = evaluate_case(case, res, judge)
        return {
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "repeat": repeat,
            "answer": res.answer,
            "route": res.route,
            "tool_calls": res.tool_calls,
            "retrieved_pages": sorted(retrieved_pages(res.policy_context)),
            "latency_s": round(latency, 2),
            "error": res.error,
            "scores": {name: s.as_dict() for name, s in scores.items()},
        }

    if workers <= 1:
        return [one(j) for j in jobs]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, jobs))


# --------------------------------------------------------------------------- summarising
def _rate(values: list[float]) -> dict:
    return {
        "n": len(values),
        "passed": int(sum(values)),
        "rate": round(sum(values) / len(values), 4) if values else None,
    }


def _collect(records: list[dict]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for rec in records:
        for name, s in rec["scores"].items():
            if s["score"] is not None:
                out[name].append(s["score"])
    return out


def summarize(records: list[dict]) -> dict:
    by_category = defaultdict(list)
    for rec in records:
        by_category[rec["category"]].append(rec)
    latencies = sorted(r["latency_s"] for r in records)
    return {
        "overall": {m: _rate(v) for m, v in _collect(records).items()},
        "by_category": {
            cat: {m: _rate(v) for m, v in _collect(recs).items()} for cat, recs in by_category.items()
        },
        "latency_s": {
            "mean": round(statistics.fmean(latencies), 2) if latencies else None,
            "p50": round(statistics.median(latencies), 2) if latencies else None,
            "p95": latencies[int(0.95 * (len(latencies) - 1))] if latencies else None,
        },
        "runs": len(records),
        "errors": sum(1 for r in records if r["error"]),
    }


def format_summary(summary: dict) -> str:
    lines = [f"{'metric':<18}{'n':>5}{'passed':>8}{'rate':>9}", "-" * 40]
    order = [m for m in METRICS if m in summary["overall"]]
    for m in order:
        s = summary["overall"][m]
        rate = f"{s['rate'] * 100:.1f}%" if s["rate"] is not None else "-"
        lines.append(f"{m:<18}{s['n']:>5}{s['passed']:>8}{rate:>9}")
    lat = summary["latency_s"]
    lines.append("-" * 40)
    lines.append(f"latency per question: mean {lat['mean']}s, p50 {lat['p50']}s, p95 {lat['p95']}s")
    lines.append(f"runs: {summary['runs']}, crashed: {summary['errors']}")
    return "\n".join(lines)


def format_failures(records: list[dict], limit: int = 60) -> str:
    rows = []
    for rec in records:
        for name, s in rec["scores"].items():
            if s["score"] == 0.0:
                rows.append(f"  {rec['id']:<5}{name:<17}{s['detail']}")
    if not rows:
        return "No failures."
    shown = rows[:limit]
    extra = f"\n  ... and {len(rows) - limit} more (see the JSON file)" if len(rows) > limit else ""
    return "Failures:\n" + "\n".join(shown) + extra


# --------------------------------------------------------------------------- real components
def make_invoke(app, label: str):
    from langchain_core.messages import HumanMessage

    def invoke(case: dict) -> CaseResult:
        state = app.invoke(
            {"messages": [HumanMessage(content=case["question"])]},
            config={
                "run_name": f"eval {case['id']}",
                "tags": ["eval", label],
                "metadata": {"case_id": case["id"], "category": case["category"]},
            },
        )
        return result_from_state(state)

    return invoke


CORRECT_SYSTEM = (
    "You are a strict grader for an HR assistant. You get a QUESTION, a REFERENCE answer written "
    "from the company handbook, and the assistant's ANSWER. Decide whether the ANSWER is correct.\n"
    "- Pass only if the ANSWER agrees with the REFERENCE on every key fact: numbers, dates, amounts, "
    "yes/no outcomes, and who or what is involved.\n"
    "- Different wording, extra correct detail, and citations like 'Source: Handbook, page 18' are fine.\n"
    "- Fail if the ANSWER contradicts the REFERENCE, omits a key fact, gives a wrong number or date, "
    "or avoids answering.\n"
    "- If the REFERENCE says the handbook does not cover something, that the employee should be asked "
    "for missing details, or that the request is out of scope, pass only if the ANSWER behaves that way "
    "and does not invent a policy.\n"
    "Give a one-sentence reason."
)
FAITHFUL_SYSTEM = (
    "You check an HR assistant's ANSWER against the handbook excerpts (CONTEXT) it was given.\n"
    "- Pass only if every factual claim in the ANSWER (numbers, durations, amounts, conditions) is "
    "supported by the CONTEXT.\n"
    "- An ANSWER that says the information is not in the handbook passes if the CONTEXT really does not contain it.\n"
    "- Ignore wording, tone and 'Source: Handbook, page N' lines.\n"
    "- Fail if the ANSWER states any fact that is not in the CONTEXT, even if it sounds plausible.\n"
    "Give a one-sentence reason."
)


def make_judge(model: str):
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from pydantic import BaseModel, Field

    class Verdict(BaseModel):
        passed: bool = Field(description="True if the answer passes.")
        reason: str = Field(description="One short sentence.")

    llm = ChatOpenAI(model=model, temperature=0).with_structured_output(Verdict)

    def judge(kind: str, **f):
        if kind == "correct":
            system = CORRECT_SYSTEM
            body = (
                f"CATEGORY: {f['category']}\nQUESTION: {f['question']}\n"
                f"REFERENCE: {f['reference']}\nANSWER: {f['answer']}"
            )
        else:
            system = FAITHFUL_SYSTEM
            body = f"CONTEXT:\n{f['context']}\n\nANSWER: {f['answer']}"
        verdict = llm.invoke([SystemMessage(content=system), HumanMessage(content=body)])
        return verdict.passed, verdict.reason

    return judge


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------- command line
def main(argv=None, app=None, judge=None) -> Path:
    """`app` and `judge` can be injected for testing; by default the real ones are built."""
    p = argparse.ArgumentParser(description="Run the PeoplePilot evaluation.")
    p.add_argument("--label", default="run", help="short name for this run, e.g. baseline")
    p.add_argument("--ids", help="comma-separated case ids to run, e.g. A04,A07")
    p.add_argument("--category", help="only run this category")
    p.add_argument("--limit", type=int, help="only run the first N selected cases")
    p.add_argument("--repeats", type=int, default=1, help="run each case N times (LLMs are not perfectly repeatable)")
    p.add_argument("--workers", type=int, default=4, help="parallel cases")
    p.add_argument("--no-judge", action="store_true", help="skip the LLM-judge metrics (answer_correct, faithful)")
    p.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", "gpt-4.1"))
    p.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    args = p.parse_args(argv)

    cases = load_cases()
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No cases selected.")

    config: dict = {}
    if app is None:
        from src import config as cfg
        from src.graph import app as real_app

        app = real_app
        config = {
            "llm_model": getattr(cfg, "LLM_MODEL", None),
            "embedding_model": getattr(cfg, "EMBEDDING_MODEL", None),
            "chunk_size": getattr(cfg, "CHUNK_SIZE", None),
            "chunk_overlap": getattr(cfg, "CHUNK_OVERLAP", None),
            "retriever_k": getattr(cfg, "RETRIEVER_K", None),
        }
    if judge is None and not args.no_judge:
        judge = make_judge(args.judge_model)
        config["judge_model"] = args.judge_model

    print(f"Running {len(cases)} cases x {args.repeats} ({args.workers} workers, label={args.label}) ...")
    start = time.perf_counter()
    records = run_cases(cases, make_invoke(app, args.label), judge, args.workers, args.repeats)
    summary = summarize(records)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    path = args.out_dir / f"{stamp}_{args.label}.json"
    path.write_text(
        json.dumps(
            {
                "label": args.label,
                "timestamp": stamp,
                "git_commit": _git_commit(),
                "config": config,
                "judge_enabled": judge is not None,
                "summary": summary,
                "cases": records,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"\nFinished in {time.perf_counter() - start:.0f}s. Saved {path}\n")
    print(format_summary(summary))
    print()
    print(format_failures(records))
    return path


if __name__ == "__main__":
    main()
