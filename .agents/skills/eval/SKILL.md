---
name: eval
description: Build or run a small eval set and record the results
---

Evaluate: (the text the user gave after the command, or their request in the message)

1. If `data/eval/` has no eval set, create 20–50 labelled examples from synthetic data, including hard cases.
2. Write a script that runs the AI component over the set and computes fitting metrics (accuracy, F1, citation correctness, or a rubric score).
3. Append results to `docs/EVAL.md`: date, model, prompt version, metrics, 3 typical failures.
4. Suggest the single change with the biggest expected gain.
