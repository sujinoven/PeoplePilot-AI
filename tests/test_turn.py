from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.turn import summarize_turn


def call(name, call_id):
    return AIMessage(content="", tool_calls=[{"id": call_id, "name": name, "args": {}}])


def result(call_id):
    return ToolMessage(content="{}", tool_call_id=call_id)


def test_only_the_latest_turn_is_summarised():
    state = {
        "messages": [
            HumanMessage(content="when does my probation end?"),
            call("calculate_probation_end", "1"),
            result("1"),
            AIMessage(content="old answer"),
            HumanMessage(content="what is the casual leave policy?"),
            AIMessage(content="new answer"),
        ],
        "route": "policy_question",
        "policy_context": "",
    }
    assert summarize_turn(state)["tools_used"] == []


def test_each_tool_is_listed_once_in_order():
    state = {
        "messages": [
            HumanMessage(content="q"),
            call("tool_a", "1"), result("1"),
            call("tool_b", "2"), result("2"),
            call("tool_a", "3"), result("3"),
            AIMessage(content="done"),
        ],
        "route": "hr_action",
    }
    assert summarize_turn(state)["tools_used"] == ["tool_a", "tool_b"]


def test_pages_come_from_the_page_tags_sorted_and_unique():
    state = {
        "messages": [HumanMessage(content="q"), AIMessage(content="a")],
        "route": "policy_question",
        "policy_context": "[Page 53]\nfoo\n\n[Page 18]\nbar\n\n[Page 18]\nbaz",
    }
    assert summarize_turn(state)["pages"] == [18, 53]


def test_an_empty_state_gives_empty_values():
    assert summarize_turn({}) == {"route": None, "tools_used": [], "pages": []}