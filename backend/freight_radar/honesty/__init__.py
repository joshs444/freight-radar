"""Machine-checked honesty — the registry-driven invariant layer (P1).

The honesty brand used to live in prose (hand-written disclaimers, per-layer verb
tuples). This package makes it executable + registry-driven:

  * `lexicon`     — one shared causal/forecast-verb list, scanned everywhere.
  * `predicates`  — pure tier / source / cost / causal-copy checks over the registry
                    (empty list == clean), reused by the CI suite AND the scorecard.
  * `scorecard`   — the acceptance harness's Layer-4 trend (scoreboard.json), minimal
                    start; never a ship gate.

See docs/plans/ACCEPTANCE-HARNESS.md (Layers 1 + 4) and STANDPOINT-VISION.md §7.
"""
