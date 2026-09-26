---
name: ladder-explain
description: Understand and document an undocumented legacy ladder station (free lint first, then bulk comments on the cheap model). Use when asked to explain, document or onboard onto a station program.
---

# Explain and document a station

1. Call `ladder_lint` for the station (for example ST20). This is free. Report the errors and warnings in plain
   language, and the comment coverage (rule L008).
2. Call `ladder_task` with `task="explain"`. It runs on the T1 lane (Gemini 3.8 Flash, low effort).
3. Present the result:
   - comment coverage before → after (from L008 and the `coverage` field);
   - 5–8 of the most useful rung purposes, by R-number;
   - anything under `suspicious`. Quote it and say that the harness ignored it;
   - the cost line from `calls` (model, dollars, tokens), labelling REPLAY if the backend was replay.
4. Do not write comments into plant files. Offer to export them with `ladder_export_gxw3` for the engineer.
