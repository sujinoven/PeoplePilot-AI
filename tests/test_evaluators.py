"""Offline tests for the evaluation pipeline (eval/evaluators.py, run_eval.py, compare.py).

No API keys: the assistant is replaced by a fake that returns "perfect" or "broken"
answers built from the dataset, and the LLM judge is replaced by a stub. If these
tests pass, a low score in a real run means the ASSISTANT is wrong, not the scorer.
"""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from eval.compare import compare
from eval.evaluators import (
    METRICS,
    CaseResult,
    asks_for_details,
    cited_pages,
    evaluate_case,
    result_from_state,
    retrieved_pages,
    values_match,
)
from eval.run_eval import format_failures, format_summary, load_cases, main, run_cases, summarize
from src.tools import HR_TOOLS

CASES = load_cases()
BY_ID = {c["id"]: c for c in CASES}
TOOLS = {t.name: t for t in HR_TOOLS}
DETERMINISTIC = [m for m in METRICS if m not in ("answer_correct", "faithful")]


# ---------------------------------------------------------------- synthetic assistants
def perfect_result(case, call_id="call-1") -> CaseResult:
    """What a flawless assistant would produce for this case."""
    calls, results = [], {}
    if case["expected_tool"]:
        args = dict(case["tool_args"])
        calls = [{"id": call_id, "name": case["expected_tool"], "args": args}]
        results = {call_id: TOOLS[case["expected_tool"]].invoke(args)}
    answer = case["reference_answer"]
    if case["category"] == "policy":
        answer += f" Source: Handbook, page {case['expected_pages'][0]}"
    if case["category"] == "action":
        answer += " " + " ".join(case["must_include"])
    if case["category"] == "needs_clarification":
        answer += " Could you share those details?"
    context = ""
    if case["category"] == "policy":
        context = "\n\n".join(f"[Page {p}]\nsome handbook text" for p in case["expected_pages"])
    if case["category"] == "not_in_handbook":
        context = "[Page 1]\nunrelated handbook text"
    return CaseResult(
        answer=answer, route=case["expected_route"], tool_calls=calls,
        tool_results=results, policy_context=context,
    )


def broken_result(case) -> CaseResult:
    """Wrong route, calls a tool that does not exist, cites nothing."""
    wrong_route = "out_of_scope" if case["expected_route"] != "out_of_scope" else "policy_question"
    return CaseResult(
        answer="I am not sure.", route=wrong_route,
        tool_calls=[{"id": "x", "name": "no_such_tool", "args": {}}], tool_results={"x": {"valid": True}},
    )


class FakeApp:
    """Stands in for the LangGraph app: returns a final state like the real one does."""

    def __init__(self, degraded_every=0):
        self.degraded_every = degraded_every  # 0 = always perfect; N = break every Nth case
        self.calls = 0

    def invoke(self, inputs, config=None):
        question = inputs["messages"][-1].content
        case = next(c for c in CASES if c["question"] == question)
        index = CASES.index(case)
        if self.degraded_every and index % self.degraded_every == 0:
            return {"messages": [HumanMessage(content=question), AIMessage(content="I am not sure.")],
                    "route": "out_of_scope" if case["expected_route"] != "out_of_scope" else "policy_question",
                    "policy_context": ""}
        res = perfect_result(case)
        messages = [HumanMessage(content=question)]
        if res.tool_calls:
            messages.append(AIMessage(content="", tool_calls=res.tool_calls))
            for c in res.tool_calls:
                messages.append(ToolMessage(content=json.dumps(res.tool_results[c["id"]]),
                                            tool_call_id=c["id"], name=c["name"]))
        messages.append(AIMessage(content=res.answer))
        return {"messages": messages, "route": res.route, "policy_context": res.policy_context}


def always_pass(kind, **fields):
    return True, "ok"


# ---------------------------------------------------------------- the dataset and the scorer agree
def test_questions_are_unique():
    assert len({c["question"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_a_perfect_answer_passes_every_deterministic_metric(case):
    scores = evaluate_case(case, perfect_result(case))
    failed = {m: s.detail for m, s in scores.items() if s.score == 0.0}
    assert not failed, failed
    assert scores["routing"].score == 1.0 and scores["tool_choice"].score == 1.0


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_a_broken_answer_fails_routing_and_tool_choice(case):
    scores = evaluate_case(case, broken_result(case))
    assert scores["routing"].score == 0.0
    assert scores["tool_choice"].score == 0.0


def test_every_applicable_metric_is_exercised_by_the_dataset():
    applied = {m for c in CASES for m, s in evaluate_case(c, perfect_result(c), always_pass).items() if s.score is not None}
    assert applied == set(METRICS)


# ---------------------------------------------------------------- parsing helpers
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Up to 45 days. Source: Handbook, page 18.", [18]),
        ("Source: Handbook, pages 18, 21", [18, 21]),
        ("see page 12 and page 53", [12, 53]),
        ("pages 12 and 53", [12, 53]),
        ("Chapter 7.2 says 45 days", []),
        ("no citation here", []),
    ],
)
def test_cited_pages(text, expected):
    assert cited_pages(text) == expected


def test_retrieved_pages_reads_the_page_tags():
    assert retrieved_pages("[Page 18]\nabc\n\n[Page 53]\ndef") == {18, 53}
    assert retrieved_pages("untagged text") == set()


@pytest.mark.parametrize(
    "got, want, expected",
    [
        ("remote_first", "remote-first", True),
        ("Remote First", "remote-first", True),
        ("EL", "el", True),
        (5, 5.0, True),
        ("5", 5, True),
        (1466.67, 1466.668, True),
        (True, 1, False),      # a bool is not a number
        (False, 0, False),
        (True, True, True),
        (None, None, True),
        (None, 0, False),
        ("2026-10-10", "2026-10-10", True),
        ("2026-10-10", "2026-10-11", False),
        (3, 4, False),
    ],
)
def test_values_match(got, want, expected):
    assert values_match(got, want) is expected


# ---------------------------------------------------------------- tool_args
def action_result(case_id, **overrides):
    """A perfect result for an action case, with some call arguments changed."""
    case = BY_ID[case_id]
    res = perfect_result(case)
    res.tool_calls[0]["args"].update(overrides)
    return case, res


def test_wrong_argument_fails_and_names_it():
    case, res = action_result("A04", days=3)
    s = evaluate_case(case, res)["tool_args"]
    assert s.score == 0.0 and "days" in s.detail


def test_an_unchecked_argument_is_allowed_to_differ():
    # A04 only checks leave_type and days; the user never said how much notice was given.
    case, res = action_result("A04", advance_days=99, is_on_probation=True)
    assert evaluate_case(case, res)["tool_args"].score == 1.0


def test_argument_naming_variants_are_accepted():
    case, res = action_result("A19", work_model="Remote_First")
    assert evaluate_case(case, res)["tool_args"].score == 1.0


def test_tool_result_that_differs_from_expected_fails():
    case, res = action_result("A04")
    res.tool_results["call-1"] = {"valid": True}
    s = evaluate_case(case, res)["tool_args"]
    assert s.score == 0.0 and "valid" in s.detail


def test_missing_tool_result_fails():
    case, res = action_result("A04")
    res.tool_results.clear()
    assert evaluate_case(case, res)["tool_args"].score == 0.0


def test_a_second_correct_call_rescues_a_wrong_first_call():
    case, res = action_result("A04", days=9)
    good = perfect_result(case, call_id="call-2")
    res.tool_calls += good.tool_calls
    res.tool_results.update(good.tool_results)
    assert evaluate_case(case, res)["tool_args"].score == 1.0


def test_tool_never_called_fails_both_tool_metrics():
    case = BY_ID["A04"]
    scores = evaluate_case(case, CaseResult(answer="No.", route="hr_action"))
    assert scores["tool_choice"].score == 0.0 and scores["tool_args"].score == 0.0


def test_a_tool_call_on_a_policy_question_fails_tool_choice():
    case = BY_ID["P01"]
    res = perfect_result(case)
    res.tool_calls = [{"id": "x", "name": "calculate_earned_leave_accrual", "args": {}}]
    assert evaluate_case(case, res)["tool_choice"].score == 0.0


# ---------------------------------------------------------------- retrieval and citations
def test_retrieval_fails_when_nothing_was_retrieved():
    case = BY_ID["P01"]
    res = perfect_result(case)
    res.policy_context = ""
    s = evaluate_case(case, res)["retrieval_hit"]
    assert s.score == 0.0 and "policy path" in s.detail


def test_retrieval_fails_when_only_other_pages_were_retrieved():
    case = BY_ID["P01"]  # expects page 18
    res = perfect_result(case)
    res.policy_context = "[Page 40]\nx\n\n[Page 41]\ny"
    assert evaluate_case(case, res)["retrieval_hit"].score == 0.0


def test_citation_hit_versus_precise():
    case = BY_ID["P03"]  # expected pages 12 and 53
    res = perfect_result(case)
    res.answer = "90 days. Source: Handbook, page 12"
    s = evaluate_case(case, res)
    assert (s["citation"].score, s["citation_precise"].score) == (1.0, 1.0)
    res.answer = "90 days. Source: Handbook, pages 12, 40"
    s = evaluate_case(case, res)
    assert (s["citation"].score, s["citation_precise"].score) == (1.0, 0.0)
    res.answer = "90 days. Source: Handbook, page 40"
    s = evaluate_case(case, res)
    assert (s["citation"].score, s["citation_precise"].score) == (0.0, 0.0)
    res.answer = "90 days."
    s = evaluate_case(case, res)
    assert (s["citation"].score, s["citation_precise"].score) == (0.0, 0.0)


def test_citation_metrics_only_apply_to_policy_cases():
    s = evaluate_case(BY_ID["A04"], perfect_result(BY_ID["A04"]))
    assert s["citation"].score is None and s["retrieval_hit"].score is None


# ---------------------------------------------------------------- clarification and keywords
def test_clarification_needs_a_question_and_no_tool():
    case = BY_ID["C01"]
    assert evaluate_case(case, perfect_result(case))["clarification"].score == 1.0
    guessed = perfect_result(case)
    guessed.tool_calls = [{"id": "x", "name": "validate_leave_request", "args": {}}]
    assert evaluate_case(case, guessed)["clarification"].score == 0.0
    statement = perfect_result(case)
    statement.answer = "Yes, you can take leave."
    assert evaluate_case(case, statement)["clarification"].score == 0.0


def test_must_include_is_case_insensitive_and_reports_missing_words():
    case = BY_ID["A17"]  # must include "Finance Head"
    res = perfect_result(case)
    res.answer = "You need FINANCE HEAD approval."
    assert evaluate_case(case, res)["must_include"].score == 1.0
    res.answer = "That is too old."
    s = evaluate_case(case, res)["must_include"]
    assert s.score == 0.0 and "Finance Head" in s.detail


# ---------------------------------------------------------------- the LLM-judge metrics
def test_judge_metrics_are_skipped_without_a_judge():
    assert "answer_correct" not in evaluate_case(BY_ID["P01"], perfect_result(BY_ID["P01"]))


def test_faithfulness_only_applies_when_there_is_retrieved_context():
    assert evaluate_case(BY_ID["A04"], perfect_result(BY_ID["A04"]), always_pass)["faithful"].score is None
    assert evaluate_case(BY_ID["P01"], perfect_result(BY_ID["P01"]), always_pass)["faithful"].score == 1.0
    assert evaluate_case(BY_ID["N01"], perfect_result(BY_ID["N01"]), always_pass)["faithful"].score == 1.0


def test_the_judge_receives_the_reference_answer_and_the_context():
    seen = {}

    def spy(kind, **fields):
        seen[kind] = fields
        return False, "nope"

    case = BY_ID["P01"]
    s = evaluate_case(case, perfect_result(case), spy)
    assert seen["correct"]["reference"] == case["reference_answer"]
    assert "[Page 18]" in seen["faithful"]["context"]
    assert s["answer_correct"].score == 0.0 and s["answer_correct"].detail == "nope"


def test_a_crashing_judge_is_not_counted_as_a_wrong_answer():
    def broken(kind, **fields):
        raise RuntimeError("rate limited")

    s = evaluate_case(BY_ID["P01"], perfect_result(BY_ID["P01"]), broken)
    assert s["answer_correct"].score is None and "rate limited" in s["answer_correct"].detail


def test_a_crashed_run_scores_zero_on_correctness():
    s = evaluate_case(BY_ID["P01"], CaseResult(error="TimeoutError: x"), always_pass)
    assert s["answer_correct"].score == 0.0 and s["routing"].score == 0.0


# ---------------------------------------------------------------- building a result from graph state
def test_result_from_state_reads_calls_results_route_and_context():
    state = {
        "messages": [
            HumanMessage(content="Can I take 4 days of CL?"),
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "validate_leave_request", "args": {"days": 4}}]),
            ToolMessage(content='{"valid": false}', tool_call_id="c1", name="validate_leave_request"),
            AIMessage(content="No. Source: Handbook, page 18"),
        ],
        "route": "hr_action",
        "policy_context": "[Page 18]\nx",
    }
    r = result_from_state(state)
    assert r.answer.startswith("No.")
    assert r.route == "hr_action"
    assert r.tool_calls == [{"id": "c1", "name": "validate_leave_request", "args": {"days": 4}}]
    assert r.tool_results == {"c1": {"valid": False}}
    assert r.policy_context == "[Page 18]\nx"


def test_result_from_state_keeps_non_json_tool_errors_as_text():
    state = {
        "messages": [
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
            ToolMessage(content="Error: bad args", tool_call_id="c1", name="t"),
            AIMessage(content="Sorry."),
        ]
    }
    assert result_from_state(state).tool_results == {"c1": "Error: bad args"}


# ---------------------------------------------------------------- the runner
def invoke_via(app):
    from eval.run_eval import make_invoke

    return make_invoke(app, "test")


def test_run_cases_preserves_order_with_parallel_workers():
    app = FakeApp()
    seq = run_cases(CASES, invoke_via(app), always_pass, workers=1)
    par = run_cases(CASES, invoke_via(app), always_pass, workers=4)
    assert [r["id"] for r in par] == [c["id"] for c in CASES]
    assert [r["scores"] for r in par] == [r["scores"] for r in seq]


def test_a_crashing_case_is_recorded_and_the_run_continues():
    def invoke(case):
        if case["id"] == "P02":
            raise RuntimeError("API down")
        return perfect_result(case)

    records = run_cases(CASES, invoke, always_pass)
    assert len(records) == len(CASES)
    bad = next(r for r in records if r["id"] == "P02")
    assert "API down" in bad["error"] and bad["scores"]["routing"]["score"] == 0.0
    assert summarize(records)["errors"] == 1


def test_repeats_multiply_the_runs():
    records = run_cases(CASES[:5], invoke_via(FakeApp()), always_pass, repeats=3)
    assert len(records) == 15 and {r["repeat"] for r in records} == {0, 1, 2}


def test_summary_counts_only_applicable_cases():
    s = summarize(run_cases(CASES, invoke_via(FakeApp()), always_pass))["overall"]
    n = {cat: sum(1 for c in CASES if c["category"] == cat) for cat in {c["category"] for c in CASES}}
    assert s["routing"]["n"] == len(CASES)
    assert s["tool_args"]["n"] == n["action"]
    assert s["retrieval_hit"]["n"] == s["citation"]["n"] == n["policy"]
    assert s["clarification"]["n"] == n["needs_clarification"]
    assert s["faithful"]["n"] == n["policy"] + n["not_in_handbook"]
    assert all(v["rate"] == 1.0 for v in s.values())


def test_summary_and_failure_text_are_readable():
    records = run_cases(CASES, invoke_via(FakeApp(degraded_every=2)), always_pass)
    summary = summarize(records)
    text = format_summary(summary)
    assert "routing" in text and "%" in text and "p95" in text
    assert 0.0 < summary["overall"]["routing"]["rate"] < 1.0
    assert "routing" in format_failures(records)
    assert format_failures([r for r in records if False]) == "No failures."


# ---------------------------------------------------------------- the command line, end to end
def test_main_writes_a_complete_results_file(tmp_path):
    path = main(["--label", "unit", "--out-dir", str(tmp_path)], app=FakeApp(), judge=always_pass)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.name.endswith("_unit.json")
    assert data["label"] == "unit" and data["judge_enabled"] is True
    assert len(data["cases"]) == len(CASES)
    assert all(v["rate"] == 1.0 for v in data["summary"]["overall"].values())


def test_main_filters_by_ids_category_and_limit(tmp_path):
    def run(*extra):
        p = main(["--out-dir", str(tmp_path), "--no-judge", *extra], app=FakeApp())
        return json.loads(p.read_text(encoding="utf-8"))["cases"]

    assert {c["id"] for c in run("--ids", "A04,P01")} == {"A04", "P01"}
    assert {c["category"] for c in run("--category", "out_of_scope")} == {"out_of_scope"}
    assert len(run("--limit", "7")) == 7


def test_main_without_a_judge_skips_the_judge_metrics(tmp_path):
    p = main(["--out-dir", str(tmp_path), "--no-judge", "--ids", "P01"], app=FakeApp())
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["judge_enabled"] is False
    assert "answer_correct" not in data["summary"]["overall"]


def test_main_rejects_an_empty_selection(tmp_path):
    with pytest.raises(SystemExit):
        main(["--out-dir", str(tmp_path), "--ids", "ZZZ"], app=FakeApp(), judge=always_pass)


# ---------------------------------------------------------------- comparing two runs
def test_compare_reports_improvements_and_regressions(tmp_path):
    before = json.loads(main(["--label", "before", "--out-dir", str(tmp_path)],
                             app=FakeApp(degraded_every=2), judge=always_pass).read_text(encoding="utf-8"))
    after = json.loads(main(["--label", "after", "--out-dir", str(tmp_path)],
                            app=FakeApp(), judge=always_pass).read_text(encoding="utf-8"))
    text = compare(before, after)
    assert "before: before" in text and "after: after" in text
    assert "Fixed (" in text and "Fixed (0)" not in text
    assert "Regressed (0): none" in text
    reverse = compare(after, before)
    assert "Regressed (0)" not in reverse and "Fixed (0): none" in reverse


# ---------------------------------------------------------------- asking for details without a "?"
@pytest.mark.parametrize(
    "answer, expected",
    [
        ("What is your grade and where are you travelling?", True),
        ("Please share your grade and the location of the trip.", True),
        ("Kindly provide your joining date.", True),
        ("To check this I'll need the number of days and the notice you plan to give.", True),
        ("Let me know your grade.", True),
        ("Yes, you can take leave next week.", False),
        ("No, Earned Leave cannot be taken during probation.", False),
        ("Your allowance is Rs 1,600 per day.", False),
    ],
)
def test_asks_for_details(answer, expected):
    assert asks_for_details(answer) is expected


def test_clarification_accepts_a_polite_request_without_a_question_mark():
    case = BY_ID["C03"]
    res = perfect_result(case)
    res.answer = "Please share your grade and the type of location you are travelling to."
    assert evaluate_case(case, res)["clarification"].score == 1.0


# ---------------------------------------------------------------- core / challenge splits
def test_main_can_run_only_the_challenge_split(tmp_path):
    p = main(["--out-dir", str(tmp_path), "--no-judge", "--split", "challenge"], app=FakeApp())
    cases = json.loads(p.read_text(encoding="utf-8"))["cases"]
    assert cases and {c["split"] for c in cases} == {"challenge"}


def test_summary_reports_each_split_separately(tmp_path):
    p = main(["--out-dir", str(tmp_path), "--no-judge"], app=FakeApp())
    summary = json.loads(p.read_text(encoding="utf-8"))["summary"]
    assert set(summary["by_split"]) == {"core", "challenge"}
    assert summary["by_split"]["core"]["routing"]["n"] == 60
    assert "headline metrics by split" in format_summary(summary)


def test_compare_prints_a_section_per_split(tmp_path):
    before = json.loads(main(["--label", "b", "--out-dir", str(tmp_path)], app=FakeApp(degraded_every=2),
                             judge=always_pass).read_text(encoding="utf-8"))
    after = json.loads(main(["--label", "a", "--out-dir", str(tmp_path)], app=FakeApp(),
                            judge=always_pass).read_text(encoding="utf-8"))
    text = compare(before, after)
    assert "[core]" in text and "[challenge]" in text


def test_compare_still_works_on_runs_saved_before_splits_existed(tmp_path):
    new = json.loads(main(["--label", "n", "--out-dir", str(tmp_path)], app=FakeApp(),
                          judge=always_pass).read_text(encoding="utf-8"))
    old = json.loads(json.dumps(new))
    del old["summary"]["by_split"]
    assert "[core]" in compare(old, new)
def test_source_fingerprint_is_recorded():
    from eval.run_eval import _source_fingerprint

    fp = _source_fingerprint()
    assert len(fp["source_hash"]) == 10
    assert fp["src_uncommitted_changes"] in (True, False, None)