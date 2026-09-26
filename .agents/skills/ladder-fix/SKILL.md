---
name: ladder-fix
description: Propose a program change and prove it on the simulator (repair loop + apply gate), then hand off a diff and GX Works3 export. Use when asked to fix a finding or implement a change on a station.
---

# Fix and prove

1. Decide the goal and the target scenarios, for example: goal "Leaking packs pass the leak test — fix the
   baseline capture"; targets `FAT-ST20-02 CE-ST20-06 FAT-ST20-09`. Use `ladder_simulate` to confirm the targets
   fail now.
2. `ladder_task` with `task="repair"`, the goal and the targets. It runs on the T3 lane. The harness rejects
   candidates that break a SAFETY rule, add lint errors, leave a target failing, or regress any other scenario,
   and feeds the reason back. Show every attempt and its stage. A rejected attempt is the point: it is the
   simulator saying no.
3. `ladder_diff` with the `candidate_path`. Show the changed rungs.
4. `ladder_apply` with the same targets. Only a pass writes `<station>/proposed.il`.
5. `ladder_export_gxw3` with `which="proposed"`. Say plainly that GX Works3 import is unverified and that an
   engineer must sign off.
