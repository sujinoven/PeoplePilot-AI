# PeoplePilot-AI
### Agentic HR Assistant using LangGraph, RAG & LangSmith

PeoplePilot-AI is an AI-powered HR Assistant built with **Python, LangGraph, LangChain, OpenAI, and Retrieval-Augmented Generation (RAG)**.

The assistant answers employee questions using the **Employee Handbook**, performs HR-related calculations and validations through custom tools, and uses **LangSmith Tracing** for monitoring and debugging agent workflows.

## Features

- **HR Policy Q&A:** Answers employee handbook questions using RAG.
- **Intelligent Query Routing:** Classifies user requests as policy questions, HR actions, or out-of-scope queries.
- **Custom HR Tools:** Validates leave requests, reimbursements, and other HR-related requests.
- **Policy-Based Explanations:** Retrieves relevant handbook policies to explain rejected requests.
- **LangGraph Workflow:** Uses state management, conditional edges, and tool-calling loops.
- **LangGraph Studio:** Visualizes and debugs graph execution.
- **LangSmith Tracing:** Tracks LLM calls, tool execution, and agent behavior.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Application development |
| LangGraph | Agent orchestration and workflow management |
| LangChain | LLM integration, RAG, and tools |
| OpenAI | Language models and embeddings |
| RAG | Employee handbook retrieval |
| InMemoryVectorStore | Vector storage |
| LangSmith | Tracing and observability |
| LangGraph Studio | Visual debugging |
| uv | Package and environment management |

## System Architecture

```text
                    Employee Question
                            |
                            v
                         Router
                            |
            +---------------+---------------+
            |               |               |
            v               v               v
      Policy Question    HR Action      Out of Scope
            |               |               |
            v               v               v
       RAG Retrieval      HR Agent       Scope Message
            |               |
            v               v
       Policy Answer     Custom Tools
            |               |
            |         Validation Result
            |               |
            |          +----+----+
            |          |         |
            |        Valid    Rejected
            |          |         |
            |          v         v
            |       HR Agent  Retrieve Policy
            |          |         |
            |          |         v
            |          |      HR Agent
            |          |         |
            +----------+---------+
                       |
                       v
                 Final Response
```

## Custom HR Tools

PeoplePilot-AI includes seven custom tools:

1. `validate_leave_request` — Validates employee leave requests.
2. `calculate_earned_leave_accrual` — Calculates earned leave accrual.
3. `calculate_probation_end` — Determines probation completion dates.
4. `check_payroll_deadline` — Checks payroll submission deadlines.
5. `validate_reimbursement_claim` — Validates reimbursement requests.
6. `calculate_remote_work_allowance` — Calculates remote-work allowances.
7. `calculate_travel_daily_allowance` — Calculates daily travel allowances.

## RAG Pipeline

The assistant retrieves relevant information from the employee handbook using:

```text
Employee Handbook (PDF)
          |
          v
      PyPDFLoader
          |
          v
  RecursiveCharacterTextSplitter
          |
          v
    OpenAI Embeddings
          |
          v
   InMemoryVectorStore
          |
          v
    Document Retriever
          |
          v
   Relevant Policy Context
          |
          v
    LLM-Generated Answer
```

The current implementation uses `text-embedding-3-small` for embeddings and `gpt-4.1-mini` for language generation.

## Project Structure

```text
PeoplePilot-AI/
├── app.py
├── langgraph.json
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── data/
│   └── PROITBRIDGE_Employee_Handbook_2026_1.pdf
└── src/
    ├── __init__.py
    ├── assistant.py
    ├── config.py
    ├── graph.py
    ├── nodes.py
    ├── edges.py
    ├── state.py
    ├── rag.py
    ├── tools.py
    └── prompts.py
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/sujinoven/PeoplePilot-AI.git
cd PeoplePilot-AI
```

### 2. Install dependencies

Ensure Python 3.11 or newer and `uv` are installed.

```bash
uv sync
```

### 3. Configure environment variables

Create a `.env` file in the project root.

```env
OPENAI_API_KEY=your_openai_api_key
LANGSMITH_API_KEY=your_langsmith_api_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=PeoplePilot-AI
```

Keep your API keys private and never commit `.env` to GitHub.

### 4. Run the HR Assistant

```bash
uv run python app.py
```

Enter your HR-related questions in the terminal. Type `exit` to close the application.

## Running LangGraph Studio

Start the LangGraph development server:

```bash
uv run langgraph dev
```

Open the Studio link displayed in the terminal.

LangGraph Studio enables visualization of the agent graph and inspection of node execution, state updates, and tool calls.

## LangSmith Tracing

LangSmith provides observability for the assistant's execution.

With tracing enabled, you can inspect:

- Query routing and graph execution
- LLM requests and responses
- Custom tool calls and outputs
- RAG-related execution
- Latency and debugging information

Open [LangSmith](https://smith.langchain.com/) and select the project configured through `LANGSMITH_PROJECT` to inspect your traces.

## Example Questions

**Policy questions**

- How many earned leave days are employees entitled to?
- What is the company's leave policy?
- What is the reimbursement policy?

**HR actions**

- Is my leave request valid?
- When will my probation period end?
- Am I eligible for a reimbursement?
- Calculate my travel daily allowance.

## Key Learnings

This project demonstrates practical implementation of:

- Agentic AI workflows
- Retrieval-Augmented Generation
- Tool calling with LangChain
- Conditional routing with LangGraph
- Stateful conversations
- Custom business logic integration
- LangSmith tracing and debugging
- Python project management with `uv`

## Limitations

- The vector store is currently in memory and rebuilt at application startup.
- Responses depend on the accuracy and currency of the employee handbook.
- HR validations are intended as decision-support demonstrations and should be reviewed before real-world use.

## Author

**GitHub:** [@sujinoven](https://github.com/sujinoven)

**Repository:** [PeoplePilot-AI](https://github.com/sujinoven/PeoplePilot-AI)

---

*Built to explore Agentic AI, intelligent HR automation, and observable AI workflows.*
