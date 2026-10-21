from typing import Literal, TypedDict

from typing_extensions import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# The three routes the router node can choose.
Route = Literal["policy_question", "hr_action", "out_of_scope"]


class HRState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]   
    route: Route
    policy_context: str   
    rejection_explained: bool
