---
description: Walk the demo flow, screenshot every step and fix the visual problems
---

Polish the UI. Scope: $ARGUMENTS

If no scope is given, polish the whole live-demo flow from `docs/PITCH.md`.

1. Start the app (with `LLM_PROVIDER=replay` if fixtures exist, so results are stable).
2. With the playwright MCP server, walk the flow step by step. Take a screenshot of each step at 1440×900 and at 1920×1080.
3. List the problems, worst first. Check:
   - broken or overlapping layout, cut-off or overflowing text, scrollbars that should not be there;
   - inconsistent spacing, alignment, radius, font sizes or colours that are not tokens from `docs/DESIGN.md`;
   - weak hierarchy: unclear primary action, AI result not the focus of its screen;
   - missing loading, empty or error states; spinners without a progress line;
   - placeholder, English or awkward text where the UI language is `de`; wrong date, number or currency format;
   - low contrast, missing focus states, unlabeled inputs;
   - anything that looks like a prototype: default favicon, "Vite App" or "Create Next App" title, raw JSON on screen.
   - every row of the "Before you finish" table in the `better-ui` skill.
4. Fix the top problems. Do not change behaviour or data flow.
5. Screenshot again and confirm each fix. End with a before/after list.
