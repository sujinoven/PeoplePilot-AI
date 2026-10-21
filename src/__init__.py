"""PROITBRIDGE HR Assistant — LangGraph + LangSmith + LangGraph Studio (Level 5).

Read the files in this order (same order as the notebook):

    1. config.py     settings, API keys, LangSmith switch
    2. tools.py      the 7 HR tools (plain Python rules)
    3. rag.py        load, split, embed, retrieve the Handbook
    4. prompts.py    one prompt per LLM node
    5. state.py      HRState: what travels through the graph
    6. nodes.py      the work done at each step
    7. edges.py      the decisions between the steps
    8. graph.py      StateGraph wiring -> compiled `app`  (Studio loads this)
    9. assistant.py  runs the graph with LangSmith run name, tags, metadata
"""
