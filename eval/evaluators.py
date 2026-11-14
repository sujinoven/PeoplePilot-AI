"""Scoring functions for the PeoplePilot evaluation.

Almost everything here is deterministic and runs offline, so it can be unit-tested.
Only two metrics (answer_correct, faithful) need an LLM; they call a `judge` function
that you pass in, so tests can use a fake one.

Each metric returns a Score: 1.0 = pass, 0.0 = fail, None = "does not apply to this case".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from langchain_core.messages import AIMessage, ToolMessage

# Order used when printing results.
METRICS = [
    "routing",           # did the router pick the right route?
    "tool_choice",       # right tool called (or no tool when none was expected)?
    "tool_args",         # right arguments, and the tool result matches the expected result?
    "clarification",     # asked for missing details instead of guessing?
    "retrieval_hit",     # did retrieval fetch a chunk from an expected handbook page?
    "citation",          # did the answer cite at least one correct page?
    "citation_precise",  # ...and are ALL cited pages correct?
    "must_include",      # does the answer contain the required keywords?
    "answer_correct",    # LLM judge: does the answer agree with the reference answer?
    "faithful",          # LLM judge: is every claim supported by the retrieved handbook text?
]


@dataclass
class CaseResult:
    """What the assistant did for one question (built from the graph's final state)."""

    answer: str = ""
    route: str | None = None
    tool_calls: list[dict] = field(default_factory=list)   # [{"id", "name", "args"}]
    tool_results: dict[str, Any] = field(default_factory=dict)  # tool_call_id -> parsed result
    policy_context: str = ""
    error: str | None = None


@dataclass
class Score:
    score: float | None
    detail: str = ""

    def as_dict(self) -> dict:
        return {"score": self.score, "detail": self.detail}


NOT_APPLICABLE = Score(None)

Judge = Callable[..., "tuple[bool, str]"]


# --------------------------------------------------------------------------- building a result
def message_text(message) -> str:
    """`.text` is a property in current langchain-core and a method in older versions."""
    text = message.text
    return str(text) if isinstance(text, str) else text()


def result_from_state(state: dict) -> CaseResult:
    """Turn the graph's final state into a CaseResult."""
    messages = state.get("messages", [])
    calls: list[dict] = []
    results: dict[str, Any] = {}
    for m in messages:
        if isinstance(m, AIMessage):
            for c in m.tool_calls or []:
                calls.append({"id": c.get("id"), "name": c["name"], "args": dict(c.get("args") or {})})
        elif isinstance(m, ToolMessage):
            raw = m.content
            try:
                parsed = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                parsed = raw
            results[m.tool_call_id] = parsed
    return CaseResult(
        answer=message_text(messages[-1]) if messages else "",
        route=state.get("route"),
        tool_calls=calls,
        tool_results=results,
        policy_context=state.get("policy_context", "") or "",
    )


# --------------------------------------------------------------------------- value comparison
def _norm(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().lower().replace("_", "-").replace(" ", "-")
        try:
            return float(s)
        except ValueError:
            return s
    return value


def values_match(got, want) -> bool:
    """Lenient comparison: case, spaces/underscores/hyphens and int-vs-float are ignored."""
    g, w = _norm(got), _norm(want)
    if isinstance(g, bool) or isinstance(w, bool):
        return isinstance(g, bool) and isinstance(w, bool) and g == w
    if isinstance(g, float) and isinstance(w, float):
        return abs(g - w) < 0.005
    return g == w


def result_mismatches(actual, expected: dict) -> list[str]:
    """expected is a subset of actual. A string ending in '*' means 'starts with'."""
    if not isinstance(actual, dict):
        return ["the tool returned no JSON result"]
    problems = []
    for key, want in expected.items():
        got = actual.get(key, "<missing>")
        if isinstance(want, str) and want.endswith("*"):
            if not (isinstance(got, str) and got.startswith(want[:-1])):
                problems.append(f"result {key}: expected {want!r}, got {got!r}")
        elif not values_match(got, want):
            problems.append(f"result {key}: expected {want!r}, got {got!r}")
    return problems


# --------------------------------------------------------------------------- page parsing
_PAGE_REF = re.compile(r"pages?\s*((?:\d+\s*(?:,|and|&|-|–)?\s*)+)", re.IGNORECASE)


def cited_pages(answer: str) -> list[int]:
    """Page numbers an answer cites, e.g. 'Source: Handbook, pages 18, 21' -> [18, 21]."""
    pages: list[int] = []
    for match in _PAGE_REF.finditer(answer):
        pages += [int(n) for n in re.findall(r"\d+", match.group(1))]
    return pages


def retrieved_pages(context: str) -> set[int]:
    """Pages of the chunks fed to the LLM, from the '[Page N]' tags added in Step 7."""
    return {int(n) for n in re.findall(r"\[Page (\d+)\]", context)}


# --------------------------------------------------------------------------- deterministic metrics
def score_routing(case: dict, res: CaseResult) -> Score:
    ok = res.route == case["expected_route"]
    return Score(float(ok), "" if ok else f"expected {case['expected_route']}, got {res.route}")


def score_tool_choice(case: dict, res: CaseResult) -> Score:
    names = [c["name"] for c in res.tool_calls]
    expected = case["expected_tool"]
    if expected:
        ok = expected in names
        return Score(float(ok), "" if ok else f"expected {expected}, called {names or 'no tool'}")
    ok = not names
    return Score(float(ok), "" if ok else f"expected no tool, called {names}")


def score_tool_args(case: dict, res: CaseResult) -> Score:
    if case["category"] != "action":
        return NOT_APPLICABLE
    tool = case["expected_tool"]
    candidates = [c for c in res.tool_calls if c["name"] == tool]
    if not candidates:
        return Score(0.0, f"{tool} was never called")
    best: list[str] | None = None
    for call in candidates:
        problems = []
        for name in case["args_to_check"]:
            want = case["tool_args"][name]
            if name not in call["args"]:
                problems.append(f"arg {name}: missing (expected {want!r})")
            elif not values_match(call["args"][name], want):
                problems.append(f"arg {name}: expected {want!r}, got {call['args'][name]!r}")
        problems += result_mismatches(res.tool_results.get(call["id"]), case["expected_result"])
        if not problems:
            return Score(1.0)
        if best is None or len(problems) < len(best):
            best = problems
    return Score(0.0, "; ".join(best or []))


def score_clarification(case: dict, res: CaseResult) -> Score:
    if case["category"] != "needs_clarification":
        return NOT_APPLICABLE
    if res.tool_calls:
        return Score(0.0, f"called {[c['name'] for c in res.tool_calls]} instead of asking")
    if "?" not in res.answer:
        return Score(0.0, "no question asked")
    return Score(1.0)


def score_retrieval(case: dict, res: CaseResult) -> Score:
    if case["category"] != "policy":
        return NOT_APPLICABLE
    if not res.policy_context.strip():
        return Score(0.0, "nothing retrieved (question did not reach the policy path)")
    got = retrieved_pages(res.policy_context)
    ok = bool(got & set(case["expected_pages"]))
    return Score(float(ok), "" if ok else f"retrieved pages {sorted(got)}, expected one of {case['expected_pages']}")


def score_citation(case: dict, res: CaseResult) -> Score:
    if case["category"] != "policy":
        return NOT_APPLICABLE
    cited = set(cited_pages(res.answer))
    if not cited:
        return Score(0.0, "no page cited")
    ok = bool(cited & set(case["expected_pages"]))
    return Score(float(ok), "" if ok else f"cited {sorted(cited)}, expected one of {case['expected_pages']}")


def score_citation_precise(case: dict, res: CaseResult) -> Score:
    if case["category"] != "policy":
        return NOT_APPLICABLE
    cited = set(cited_pages(res.answer))
    if not cited:
        return Score(0.0, "no page cited")
    wrong = cited - set(case["expected_pages"])
    return Score(float(not wrong), "" if not wrong else f"cited wrong pages {sorted(wrong)}")


def score_must_include(case: dict, res: CaseResult) -> Score:
    if not case["must_include"]:
        return NOT_APPLICABLE
    missing = [s for s in case["must_include"] if s.lower() not in res.answer.lower()]
    return Score(float(not missing), "" if not missing else f"answer is missing {missing}")


# --------------------------------------------------------------------------- LLM-judge metrics
def score_answer_correct(case: dict, res: CaseResult, judge: Judge) -> Score:
    passed, reason = judge(
        "correct",
        question=case["question"],
        reference=case["reference_answer"],
        answer=res.answer,
        category=case["category"],
    )
    return Score(float(passed), reason)


def score_faithful(case: dict, res: CaseResult, judge: Judge) -> Score:
    if case["category"] not in ("policy", "not_in_handbook") or not res.policy_context.strip():
        return NOT_APPLICABLE
    passed, reason = judge("faithful", context=res.policy_context, answer=res.answer)
    return Score(float(passed), reason)


# --------------------------------------------------------------------------- one case
def evaluate_case(case: dict, res: CaseResult, judge: Judge | None = None) -> dict[str, Score]:
    scores = {
        "routing": score_routing(case, res),
        "tool_choice": score_tool_choice(case, res),
        "tool_args": score_tool_args(case, res),
        "clarification": score_clarification(case, res),
        "retrieval_hit": score_retrieval(case, res),
        "citation": score_citation(case, res),
        "citation_precise": score_citation_precise(case, res),
        "must_include": score_must_include(case, res),
    }
    if judge is not None:
        if res.error:
            scores["answer_correct"] = Score(0.0, f"run failed: {res.error}")
            scores["faithful"] = NOT_APPLICABLE
        else:
            for name, fn in (("answer_correct", score_answer_correct), ("faithful", score_faithful)):
                try:
                    scores[name] = fn(case, res, judge)
                except Exception as exc:  # a broken judge call must not look like a failed answer
                    scores[name] = Score(None, f"judge error: {type(exc).__name__}: {exc}")
    return scores
