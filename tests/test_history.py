"""Offline tests for the history the router sees (src/history.py)."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.history import routing_history


def test_tool_messages_and_tool_call_turns_are_dropped():
    msgs = [
        HumanMessage(content="Can I take EL?"),
        AIMessage(
            content="",
            tool_calls=[{"name": "validate_leave_request", "args": {}, "id": "c1"}],
        ),
        ToolMessage(content='{"valid": false}', tool_call_id="c1"),
        AIMessage(content="No, you are on probation."),
        HumanMessage(content="What about CL?"),
    ]
    out = routing_history(msgs)
    assert [m.content for m in out] == [
        "Can I take EL?",
        "No, you are on probation.",
        "What about CL?",
    ]


def test_only_last_six_turns_are_kept():
    msgs = [HumanMessage(content=str(i)) for i in range(10)]
    assert [m.content for m in routing_history(msgs)] == ["4", "5", "6", "7", "8", "9"]


def test_short_reply_keeps_the_clarifying_question_before_it():
    msgs = [
        HumanMessage(content="Can I take leave?"),
        AIMessage(content="Which type and how many days?"),
        HumanMessage(content="EL, 5 days"),
    ]
    assert routing_history(msgs)[-2].content == "Which type and how many days?"