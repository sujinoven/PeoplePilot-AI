#Main purpose is to connect the user's HR question to the compiled langgraph workflow.and
import uuid

from langchain_core.messages import HumanMessage

from .config import LLM_MODEL
from langgraph.checkpoint.memory import InMemorySaver

from .graph import graph
#Here we'll run the graph using Invoke and return the final answer

class HRAssistant:
    def __init__(self) -> None:
        self.session_id = str(uuid.uuid4())
        self.app = graph.compile(checkpointer=InMemorySaver())

    def ask(self, question: str) -> str:  #Accepts a question as a string and prepares it for langgraph.
        inputs = {"messages": [HumanMessage(content=question)]}
        config = {
            "run_name": "HR Assistant",
            "tags": ["hr-assistant", "level-5"],
            "metadata": {"session_id": self.session_id, "llm_model": LLM_MODEL},
            "configurable": {"thread_id": self.session_id},
        }
        result = self.app.invoke(inputs, config=config)
        return result["messages"][-1].text
