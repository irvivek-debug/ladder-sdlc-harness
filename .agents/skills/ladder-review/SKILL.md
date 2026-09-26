---
name: ladder-review
description: Engineering review of a station program against its narrative, parameter sheet and C&E matrix — simulator evidence first, then the premium reviewer. Use when asked to review, audit or find bugs in a station.
---

# Review a station

1. `ladder_lint` (free), then `ladder_simulate` (free). Note which scenarios fail. They are hard evidence.
2. `ladder_task` with `task="review"`. It runs on the T4 lane (Claude Opus 5.5 on Vertex).
3. Present a findings table ranked by severity: title, rungs, devices, consequence on the plant, proposed fix.
   For each finding, name the failing scenario that proves it, or mark it "not yet proven".
4. Call out findings that only the reviewer found, which neither lint nor a failing scenario flagged. That is
   where the premium model earns its cost.
5. End with the cost of the call and the reminder that nothing has been changed yet.
