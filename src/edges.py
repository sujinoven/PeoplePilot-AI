import json
from langchain_core.messages import AIMessage, ToolMessage
from .state import HRState


def route_question(state: HRState) -> str:
    """Branch 1: send the question down the right path."""
    return state["route"]  # "policy_question" | "hr_action" | "out_of_scope"


def after_hr_tools(state: HRState) -> str:
    """Branch 2: did a validation tool REJECT the request?

    - Yes, and we have not explained it yet -> "explain_rejection"
      (detour through retrieve_policy to fetch the rule behind the rejection)
    - Otherwise                             -> "hr_agent"
      (the normal agent <-> tools loop)
    """
    rejected = False

    # Look only at the tool results produced since the last AI message.
    for message in reversed(state["messages"]):
        if isinstance(message, AIMessage):
            break
        if isinstance(message, ToolMessage):
            # ToolNode stores the tool's dict as a JSON string.
            result = json.loads(message.content)
            if result.get("valid") is False:
                rejected = True

    if rejected and not state.get("rejection_explained"):
        return "explain_rejection"
    return "hr_agent"


def after_retrieval(state: HRState) -> str:
    """Branch 3: retrieve_policy is shared by two paths -- where do we go next?"""
    if state.get("route") == "hr_action":
        return "hr_agent"       # came from the explain-rejection detour
    return "policy_answer"      # came straight from the router
