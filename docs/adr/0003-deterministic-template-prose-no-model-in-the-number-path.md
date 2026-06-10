# 3. Deterministic template prose — no model in the number path

Status: Accepted
Date: 2026-06-05

## Context

The app renders plain-English narrative everywhere a number appears: the per-flag
brief ("Shanghai port calls fell to 18 on 2026-05-25, 79% below its 28-day norm,
z = −7.1"), the weekly "this week" hero card, and the grounded chat. The obvious
way to produce that prose is to hand the figures to an LLM and let it write.

Doing so would put a model **in the number path**: a model that paraphrases a
figure can also misstate it, and for a project whose entire brand is "every
number traces to source," a single hallucinated statistic is a brand-level
failure. The narrative is therefore a place where the cheap, generative option is
the wrong one.

## Decision

Every narrative figure is **string-substituted into a fixed template from a
real, Python-computed value**. No model is called to produce any number, so no
model can invent one. The weekly brief (`narrative/brief.py`) assembles its
bullets from already-computed sidecars (flags / stress / market / exposure /
news / events) and substitutes the computed values into template strings. The
chat (ADR not separate — see "How it stays honest") only ever states a number it
can cite to a source sidecar, enforced by a test.

A stub seam is left for an **optional local-LLM wording polish** on new flags
(`temporal/activities.py` `_Attributor`), but it is structurally forbidden from
touching a figure, and production prose is template-only by default — the default
attributor is a pass-through that returns the template brief unchanged and makes
no external call.

## Consequences

- No statistic on the page can be hallucinated, because no statistic passes
  through a generative model. This is enforced, not merely asserted: the chat's
  grounding test runs the engine over a battery of questions and fails if any
  cited fact is not found in its source sidecar.
- The prose is less fluid than free-form generation would be — it reads as
  assembled templates. That is the intended trade: legibility and provenance over
  polish.
- The narrative layer is deterministic and zero-marginal-cost: the same inputs
  always produce the same prose, with no API key, no token bill, and no
  per-render model latency.
- An optional local-model polish remains available as a clearly bounded seam that
  can only rewrite wording, never numbers — so the door to nicer prose is open
  without ever reopening the door to a fabricated figure.
