"""Offline tests for the graph's routing decisions (src/edges.py).

edges.py reads ToolMessage.content as JSON, so these tests build ToolMessages the
same way LangGraph's ToolNode does and check which branch is chosen.
"""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.edges import after_hr_tools, after_retrieval, route_question


def tool_msg(result, call_id="c1", **kwargs):
    content = result if isinstance(result, str) else json.dumps(result)
    return ToolMessage(content=content, tool_call_id=call_id, **kwargs)


def state(*messages, **extra):
    return {"messages": list(messages), **extra}


# ---------------------------------------------------------------------------
# route_question / after_retrieval
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("route", ["policy_question", "hr_action", "out_of_scope"])
def test_route_question_passes_router_decision_through(route):
    assert route_question({"route": route}) == route


def test_after_retrieval_policy_question_goes_to_policy_answer():
    assert after_retrieval({"route": "policy_question"}) == "policy_answer"


def test_after_retrieval_from_rejection_detour_goes_back_to_agent():
    assert after_retrieval({"route": "hr_action"}) == "hr_agent"


# ---------------------------------------------------------------------------
# after_hr_tools
# ---------------------------------------------------------------------------
class TestAfterHrTools:
    def test_rejection_triggers_policy_detour(self):
        s = state(
            HumanMessage(content="Can I take 5 days of EL in probation?"),
            AIMessage(content=""),
            tool_msg({"valid": False, "reason": "no"}),
        )
        assert after_hr_tools(s) == "explain_rejection"

    def test_valid_result_returns_to_agent(self):
        s = state(HumanMessage(content="q"), AIMessage(content=""), tool_msg({"valid": True}))
        assert after_hr_tools(s) == "hr_agent"

    def test_undefined_result_none_is_not_treated_as_rejection(self):
        """The 16-45 day reimbursement window returns valid=None on purpose."""
        s = state(HumanMessage(content="q"), AIMessage(content=""), tool_msg({"valid": None}))
        assert after_hr_tools(s) == "hr_agent"

    def test_rejection_is_only_explained_once(self):
        s = state(
            HumanMessage(content="q"),
            AIMessage(content=""),
            tool_msg({"valid": False}),
            rejection_explained=True,
        )
        assert after_hr_tools(s) == "hr_agent"

    def test_old_rejection_before_latest_ai_message_is_ignored(self):
        s = state(
            HumanMessage(content="q"),
            AIMessage(content=""),
            tool_msg({"valid": False}, call_id="old"),
            AIMessage(content="thinking again"),
            tool_msg({"valid": True}, call_id="new"),
        )
        assert after_hr_tools(s) == "hr_agent"

    def test_one_rejection_among_parallel_tool_calls_is_enough(self):
        s = state(
            HumanMessage(content="q"),
            AIMessage(content=""),
            tool_msg({"valid": True}, call_id="a"),
            tool_msg({"valid": False}, call_id="b"),
        )
        assert after_hr_tools(s) == "explain_rejection"

   
    def test_non_json_tool_error_does_not_crash_the_graph(self):
        s = state(
            HumanMessage(content="q"),
            AIMessage(content=""),
            tool_msg("Error: 1 validation error for validate_leave_request", status="error"),
        )
        assert after_hr_tools(s) == "hr_agent"
