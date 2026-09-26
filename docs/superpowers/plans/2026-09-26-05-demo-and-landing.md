# Plan 5 — Demo and Landing

> Executed inline. Spec §8 (demo), §9 (landing), §11 (success criteria).

## Tasks
1. **Preflight** — `ladder preflight`: login (ADC) and project set; each routed model reachable, checked with a
   single tiny call or a recorded cassette; pricing no older than 14 days; demo cassettes present; mode
   recommendation (live or replay).
2. **Demo cassettes** — `scripts/pin_demo_cassettes.py`: pick the epoch per demo task from the sweep. For RP-D5,
   prefer a run whose first attempt was rejected. Re-key those epoch-tagged cassettes as untagged, so the stage
   demo replays a real recorded run on the routed lanes.
3. **Pages** — `scripts/build_demo_pages.py` fills `demo/story.html` (beat 1) and `demo/ledger.html` (beat 6) from
   `evals/results/summary.json`, so no number on stage is typed by hand. Restrained design, light and dark themes,
   usable at 390 px. The one external figure (McKinsey, 27 June 2023, verified on the page) sits beside the
   harness's own measured number.
4. **Runbook and scripts** — `demo/RUNBOOK.md` (7 beats: exact prompts, timing, expected output, fallback, reset),
   `demo/run_headless.sh` (the arc through `agy -p … --output-format json`, asserting SUCCESS),
   `demo/reset.sh`, `demo/playground/CHALLENGES.md`.
5. **Repo hygiene** — `README.md` (60-second replay quickstart), `.github/workflows/ci.yml` (tests in replay mode
   with no credentials), `scripts/secret_scan.sh`, and `scripts/scrub_check.py` (project IDs, emails, home paths,
   customer-pursuit wording; required before any public flip).
6. **Cloud Shell verification** — copy the repo with `gcloud cloud-shell scp`, install, and run `demo/run_headless.sh`
   through `agy`. Record the results in the RUNBOOK.
7. **Landing** — local commits and the secret scan; ask before pushing to a private `irvivek-debug/ladder-sdlc-harness`.
