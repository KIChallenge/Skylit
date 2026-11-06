---
name: propose
description: Split a request into pool tasks and post them to the queue
---

Split this into tasks for the team pool: (the text the user gave after the command, or their request in the message)

Read `hackkit task list` and `hackkit manager show` first, so you do not duplicate work.
Each task must take one agent 15–40 minutes and touch files no other open task touches.
For each task, run:

    hackkit task create --title "<imperative title>" --agent <claude|codex|agy> --files "<path>,<path>" --test "<command>" --body "<goal and acceptance criteria>"

Pick the agent by job: claude for UI screens, hard logic and design, codex for parallel implementation, agy for reading large data, tests, scripts and docs.
Show the list of created tasks at the end.
