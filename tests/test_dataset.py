"""Offline checks that the evaluation dataset (eval/dataset.jsonl) is trustworthy.

A wrong label makes every evaluation number meaningless, so these tests check the
labels against the two sources of truth, with no OpenAI key:

  * the handbook PDF  -> every evidence quote exists, on the pages we say it does
  * the real HR tools -> every action case's expected_result is what the tool returns
"""

import json
from functools import lru_cache
from pathlib import Path

import pytest
from pypdf import PdfReader

from src.tools import HR_TOOLS

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "eval" / "dataset.jsonl"
HANDBOOK = ROOT / "data" / "Employee_Handbook.pdf"

TOOLS = {t.name: t for t in HR_TOOLS}
ROUTES = {"policy_question", "hr_action", "out_of_scope"}
CATEGORIES = {"policy", "not_in_handbook", "action", "needs_clarification", "out_of_scope"}
REQUIRED = {
    "id", "category", "question", "expected_route", "expected_tool", "tool_args",
    "args_to_check", "expected_result", "reference_answer", "must_include", "evidence",
    "expected_pages", "handbook_section", "expect_clarification", "expect_not_found",
    "absence_terms", "tags", "split",
}


def norm(text: str) -> str:
    """Lower-case and drop all whitespace, so line breaks and column layout in the PDF don't matter."""
    return "".join(text.lower().split())


@lru_cache(maxsize=1)
def pdf_pages() -> list[str]:
    """Normalised text of every page. Index 0 is printed page 1, matching the footer numbers."""
    return [norm(p.extract_text() or "") for p in PdfReader(str(HANDBOOK)).pages]


def pages_containing(snippets) -> list[int]:
    return [i + 1 for i, text in enumerate(pdf_pages()) if all(norm(s) in text for s in snippets)]


def matches(actual: dict, expected: dict) -> bool:
    """expected is a subset of actual. A string ending in '*' means 'starts with'."""
    for key, want in expected.items():
        got = actual.get(key, "<missing>")
        if isinstance(want, str) and want.endswith("*"):
            if not (isinstance(got, str) and got.startswith(want[:-1])):
                return False
        elif got != want:
            return False
    return True


CASES = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]
BY_ID = {c["id"]: c for c in CASES}
ids = lambda cases: [c["id"] for c in cases]  # noqa: E731

POLICY_LIKE = [c for c in CASES if c["evidence"]]
ACTIONS = [c for c in CASES if c["category"] == "action"]
ABSENCE = [c for c in CASES if c["absence_terms"]]


def test_ids_are_unique():
    assert len(BY_ID) == len(CASES)


def test_dataset_covers_every_category_and_every_tool():
    assert len(CASES) >= 50
    assert {c["category"] for c in CASES} == CATEGORIES
    assert {c["expected_tool"] for c in ACTIONS} == set(TOOLS)


def test_core_split_is_frozen_and_a_challenge_split_exists():
    core = [c for c in CASES if c["split"] == "core"]
    challenge = [c for c in CASES if c["split"] == "challenge"]
    assert len(core) == 60, "the core split is the baseline: never add or remove cases from it"
    assert len(challenge) >= 20
    assert {c["split"] for c in CASES} == {"core", "challenge"}
    assert all(c["id"].startswith("X") for c in challenge)
    assert not any(c["id"].startswith("X") for c in core)


@pytest.mark.parametrize("case", CASES, ids=ids(CASES))
def test_case_is_well_formed(case):
    assert REQUIRED <= set(case), f"missing keys: {REQUIRED - set(case)}"
    assert case["category"] in CATEGORIES
    assert case["expected_route"] in ROUTES
    assert case["question"].strip() and case["reference_answer"].strip()
    if case["category"] == "out_of_scope":
        assert case["expected_route"] == "out_of_scope"
    else:
        assert case["expected_route"] != "out_of_scope"
    if case["category"] == "needs_clarification":
        assert case["expect_clarification"] is True and case["expected_tool"] is None
    if case["category"] == "not_in_handbook":
        assert case["expect_not_found"] is True


@pytest.mark.parametrize("case", POLICY_LIKE, ids=ids(POLICY_LIKE))
def test_evidence_exists_on_the_listed_pages(case):
    expected_pages = set()
    for group in case["evidence"]:
        found = pages_containing(group)
        assert found, f"quote not found in the handbook: {group}"
        expected_pages.update(found)
    assert sorted(expected_pages) == sorted(case["expected_pages"])


@pytest.mark.parametrize("case", ABSENCE, ids=ids(ABSENCE))
def test_unanswerable_questions_really_are_absent_from_the_handbook(case):
    for term in case["absence_terms"]:
        assert not pages_containing([term]), f"{term!r} IS in the handbook, so this is answerable"


@pytest.mark.parametrize("case", ACTIONS, ids=ids(ACTIONS))
def test_action_expectation_matches_the_real_tool(case):
    tool = TOOLS[case["expected_tool"]]
    actual = tool.invoke(case["tool_args"])
    assert matches(actual, case["expected_result"]), f"tool returned {actual}"
    assert set(case["args_to_check"]) <= set(case["tool_args"]), "args_to_check names an unknown argument"
