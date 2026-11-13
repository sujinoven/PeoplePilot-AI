from langchain_core.messages import AIMessage, HumanMessage


def routing_history(messages, limit: int = 6):
    """Plain-text human/assistant turns only, last `limit` of them.

    Tool calls and tool results are dropped so the router never receives a
    tool message without its matching tool call.
    """
    turns = [
        m
        for m in messages
        if isinstance(m, (HumanMessage, AIMessage))
        and m.text
        and not getattr(m, "tool_calls", None)
    ]
    return turns[-limit:]