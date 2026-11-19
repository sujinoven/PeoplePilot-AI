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
