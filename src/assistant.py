import uuid

from langchain_core.messages import HumanMessage

from .config import LLM_MODEL
from .graph import app


class HRAssistant:
    def __init__(self) -> None:
        self.session_id = str(uuid.uuid4())

    def ask(self, question: str) -> str:
        inputs = {"messages": [HumanMessage(content=question)]}
        config = {
            "run_name": "HR Assistant",
            "tags": ["hr-assistant", "level-5"],
            "metadata": {"session_id": self.session_id, "llm_model": LLM_MODEL},
        }
        result = app.invoke(inputs, config=config)
        return result["messages"][-1].text
