---
description: Generate realistic synthetic data for a schema
---

Generate synthetic data for: $ARGUMENTS

- Write a script in `scripts/` that generates the data with a fixed random seed, so it is reproducible.
- Make it realistic for the domain and language `de`: plausible names, dates, codes and free text, but all invented.
- Include edge cases: missing fields, typos, conflicting values, very long texts.
- Write the output to `data/synthetic/` and describe the fields in `data/synthetic/README.md`.
- Never copy real records. Mark every file as synthetic.
