#function that summarises only the latest turn.
import re

from langchain_core.messages import AIMessage, HumanMessage

PAGE_TAG = re.compile(r"\[Page (\d+)\]")


def summarize_turn(state: dict) -> dict:
    """What happened in the LATEST turn only (the state keeps the whole conversation)."""
    messages = state.get("messages", [])
    last_human = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=-1)
    tools_used: list[str] = []
    for message in messages[last_human + 1:]:
        if isinstance(message, AIMessage):
            for tool_call in message.tool_calls or []:
                if tool_call["name"] not in tools_used:
                    tools_used.append(tool_call["name"])
    pages = sorted({int(n) for n in PAGE_TAG.findall(state.get("policy_context") or "")})
    return {"route": state.get("route"), "tools_used": tools_used, "pages": pages}