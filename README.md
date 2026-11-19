# PeoplePilot-AI
### Agentic HR Assistant using LangGraph, RAG & LangSmith
Problem Statement

In organizations, employees frequently contact HR for information about leave policies, reimbursements, payroll deadlines, probation periods and allowances.

Answering these repetitive questions manually consumes time and effort.

So, the objective of my project is to build an intelligent assistant that can understand employee questions and provide answers or perform HR-related calculations automatically.

## Features

- **HR Policy Q&A:** Answers employee handbook questions using RAG.
- **Intelligent Query Routing:** Classifies user requests as policy questions, HR actions, or out-of-scope queries.
- **Custom HR Tools:** Validates leave requests, reimbursements, and other HR-related requests.
- **Policy-Based Explanations:** Retrieves relevant handbook policies to explain rejected requests.
- **Conversation Memory:** Per-session threads (`InMemorySaver`), so follow-up questions keep context.
- **Page-Level Citations:** Policy answers cite handbook pages as `[Page N]`.
- **Evaluation Suite:** 110-case dataset with automated metrics and an LLM judge (see [Evaluation](#evaluation)).
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

LLM decides which tool to call and ToolNode(nodes.py) executes that tool and returns that conversation.

```text
                    Employee Question
                            |
                            v
                         Router(LLM)
                            |
            +---------------+---------------+
            |               |               |
            v               v               v
      Policy Question    HR Action      Out of Scope(No LLM)
            |               |               |
            v               v               v
       RAG Retrieval      HR Agent(LLM)      Scope Message
            |               |
            v               v
       Policy Answer(LLM)    Custom Tools
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


The assistant uses `text-embedding-3-small` for embeddings and `gpt-4.1-mini` for generation. Evaluation answers are graded by `gpt-4.1`.

## Project Structure

```text
PeoplePilot-AI/
├── app.py                  # CLI chat loop
├── langgraph.json
├── pyproject.toml
├── uv.lock
├── requirements.txt
├── data/
│   └── Employee_Handbook.pdf
├── src/
│   ├── __init__.py
│   ├── assistant.py        # HRAssistant (one conversation thread per instance)
│   ├── config.py
│   ├── graph.py
│   ├── nodes.py
│   ├── edges.py
│   ├── state.py
│   ├── rag.py
│   ├── history.py
│   ├── tools.py
│   ├── prompts.py
│   ├── turn.py             # per-turn summary (route, tools, pages)
│   ├── sessions.py         # bounded per-session store
│   └── api.py              # FastAPI backend (in progress)
├── eval/
│   ├── dataset.jsonl       # 110 labelled cases
│   ├── run_eval.py         # runs the assistant, scores, saves results
│   ├── evaluators.py
│   ├── compare.py          # before/after comparison of two runs
│   ├── failures.py
│   ├── show.py
│   └── results/            # saved runs
└── tests/                  # 666 offline tests
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

## Testing

```bash
uv run pytest tests -q
```

666 offline tests (no API calls) cover the HR tools, graph edges, retrieval formatting, dataset labels, the evaluation harness and the API layer.

## Evaluation

The assistant is evaluated against a handbook-grounded dataset (`eval/dataset.jsonl`, 110 cases) with an
automated harness (`uv run python -m eval.run_eval`). Every number below comes from a saved run in
`eval/results/` that records the git commit, a hash of `src/`, and the model configuration.

### Dataset

| Split | Cases | Purpose |
|---|---|---|
| `core` | 60 | Frozen baseline set. I looked at its failures while tuning, so it is not a clean test. |
| `challenge` | 28 | Harder and borderline cases. Also partly used while tuning. |
| `holdout` | 22 | Written after tuning, from handbook sections no other case touches. Run only on request (`--split holdout`). |

Categories: policy questions, questions the handbook does not answer, tool actions (all 7 HR tools),
questions that need clarification, and out-of-scope questions. Every label is checked offline against the
handbook PDF (evidence quotes on the listed pages) and against the real tools (expected results).

### Metrics

Routing, tool choice, tool arguments, clarification, retrieval hit, page citation (any expected page, and
precise: no unexpected pages), plus two LLM-judge metrics (gpt-4.1, scored against a reference answer):
answer correctness and faithfulness to the retrieved context.

### Results: original system vs final system

Original = prompts before the router work. Final = router redesigned around tool coverage, a scope rule that
covers the whole handbook, and "suggest asking HR when the handbook is silent". Same dataset, same code, same
judge. Counts are runs (each case runs 3 times).

**Core + challenge (88 cases)**

| Metric | Original | Final |
|---|---|---|
| Routing | 246/264 (93.2%) | 258/264 (97.7%) |
| Tool choice | 252/264 (95.5%) | 261/264 (98.9%) |
| Tool arguments | 93/99 (93.9%) | 99/99 (100%) |
| Retrieval hit | 99/108 (91.7%) | 105/108 (97.2%) |
| Citation | 96/108 (88.9%) | 102/108 (94.4%) |
| Answer correctness | 250/264 (94.7%) | 260/264 (98.5%) |
| Faithfulness | 114/114 (100%) | 120/120 (100%) |

Core alone: routing 171/180 -> 180/180, answer correctness 174/180 -> 180/180 (tuned on, so optimistic).
Challenge alone: routing 75/84 -> 78/84, answer correctness 76/84 -> 80/84.

**Holdout (22 fresh cases)**

| Metric | Original | Final |
|---|---|---|
| Routing | 60/66 (90.9%) | 63/66 (95.5%) |
| Tool choice | 66/66 (100%) | 63/66 (95.5%) |
| Retrieval hit | 24/30 (80.0%) | 30/30 (100%) |
| Citation | 24/30 (80.0%) | 29/30 (96.7%) |
| Answer correctness | 58/66 (87.9%) | 66/66 (100%) |
| Faithfulness | 30/30 (100%) | 36/36 (100%) |

The holdout exposed a real bug: a question about pasting client data into an AI chatbot was routed to
`out_of_scope`, because the router thought "AI chatbot" was off-topic. I fixed the router's scope rule after
seeing it, so that case (H07) is no longer held out. On the 21 untouched cases: answer correctness 58/63
(92.1%) -> 63/63 (100%), retrieval 24/27 (88.9%) -> 27/27 (100%), routing unchanged at 60/63 (95.2%).

### How to read these numbers

- **Repeats are not independent.** At temperature 0 a given case usually gives the same answer on all 3
  repeats, so the real sample is about the number of cases (88, and 22), not 264 and 66. One case flipping is
  3 runs. Differences of one or two cases are within noise.
- **Borderline cases.** XP03, XP04 and H10 are "Can I ...?" questions about probation or leave with no
  details. Both routes (policy or leave-validation tool) can answer them correctly, and H10 flipped between
  two runs of identical prompts. They are kept as labelled and reported as failures.
- **The judge is strict about extra facts.** XN01 fails because the answer adds a true fact (salary is paid
  by NEFT) that is not in the reference.
- **The handbook contradicts itself on gratuity timing** (30 days on p.54, 45 days for the full and final
  settlement on pp.52 and 55). The case accepts either.

### Corrections made after seeing results

Labels were corrected only when the model's answer was right and my label was incomplete. Every correction
changes a label, never a score. Metrics for the core split other than citation are unaffected.

- XP01: reference now includes the written-refusal exception.
- XP03, XP04, XP06, H10, H07, P09 (core): expected pages now include every page where the rule is stated.
- XA01, XA03: questions now state the inputs the tool requires (probation status, notice given).
- XP09: reference accepts both handbook timelines.

### What changed in the system

Router prompt (tool-coverage rule, "tools win" precedence, whole-handbook scope), policy answer prompt
(suggest asking HR when the handbook is silent), plus earlier code fixes found by tests against the handbook
(payroll weekend rule, manager probation, half-day leave, route history, handbook page citations).
666 offline tests cover the tools, graph edges, retrieval formatting, the dataset labels and the
evaluation harness itself.

### Reproduce

```
uv run python -m eval.run_eval --label mylabel --repeats 3 --workers 2
uv run python -m eval.run_eval --label mylabel-holdout --split holdout --repeats 3
uv run python -m eval.compare eval/results/BEFORE.json eval/results/AFTER.json
```

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
- Measuring LLM systems: held-out sets, one-change-at-a-time prompt work, LLM-as-judge, and tying every run to a git commit
- Test-first development with offline fakes

## Limitations

- The vector store is currently in memory and rebuilt at application startup.
- Responses depend on the accuracy and currency of the employee handbook.
- Sessions are held in memory in a single process; history is lost on restart.
- Evaluation repeats are highly correlated at temperature 0, so the effective sample is about the number of cases (88 core+challenge, 22 holdout).
- A few borderline cases (XP03, XP04, H10) can be answered correctly by either route and are reported as failures.
- The handbook contradicts itself on gratuity timing (30 vs 45 days); the evaluation accepts both.
- HR validations are intended as decision-support demonstrations and should be reviewed before real-world use.

## Author

**GitHub:** [@sujinoven](https://github.com/sujinoven)

**Repository:** [PeoplePilot-AI](https://github.com/sujinoven/PeoplePilot-AI)

---

*Built to explore Agentic AI, intelligent HR automation, and observable AI workflows.*
