from typing import Literal, TypedDict

from typing_extensions import Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# The three routes the router node can choose.
Route = Literal["policy_question", "hr_action", "out_of_scope"]

#State is an shared memory that will pass through all th edges in the particular graph.A shared workflow memory
class HRState(TypedDict, total=False): #Custom graph state class
    messages: Annotated[list[AnyMessage], add_messages]   
    route: Route  #Stores  the routing decision
    policy_context: str   #Stores the retrieved policy information
    rejection_explained: bool #Tracks whether the request was rejected to the user
