# I made honesty a compile error

I build a thing called [Standpoint](https://joshs444.github.io/freight-radar/) — a 3D globe that watches the world's ocean-freight chokepoints, flags the ones statistically falling apart, and rings them with cited world context. The whole pitch is one sentence: *every number on the screen traces back to source, and nothing forecasts.* No "live." No "real-time." No model in the number path. No co-occurrence quietly upgraded into a cause.

That sentence is easy to write in a README and almost impossible to keep true. Honesty isn't a feature you ship once; it's a property that decays on every commit. Someone — often me, six weeks later, in a hurry — adds an import, widens a search, paraphrases a figure through a language model "just for the wording," and the brand-level promise springs a leak nobody notices until a reader does.

So I stopped treating honesty as a thing I promise and started treating it as a thing I **compile**. The failure modes of an honest data product are structural, and structural things can be checked by a machine on every push. Here are the four I made into failing builds, the bugs they caught, and the part where the check caught *me*.

---

## 1. A boundary the import graph enforces, not a comment

The cardinal rule of the system: a *context* layer — news, storms, an AI's prose — may **read** a measured number, but it may never **write** one. The fact-writer is quarantined. Everything else is downstream of it and read-only.

You can write that rule as a comment. The comment will be ignored — not maliciously, just by entropy. The first time someone needs a number inside a context module, `from ..facts import compute` is *right there*, it works, the tests pass, and the boundary is gone. No reviewer catches every import in every PR forever.

So the rule isn't a comment. It's a static BFS over the import graph that runs in CI:

```python
FORBIDDEN = ("freight_radar.derived",)  # the AI-output tier; nothing may import back from it

for module in modules_under("freight_radar", "freight_radar"):
    assert forbidden_reach("freight_radar", module, FORBIDDEN) == set()
```

It walks the *entire* AST, so it follows a lazy `from ..facts import write` buried inside a function body, not just the top-of-file imports. A violation isn't a smell to argue about in review. It's a red X.

**The receipt:** this check caught its own author. Twice. I was wiring an honesty *scorecard* and gave it an import of the abstention gate — which, two hops down the graph, reached the quarantined `derived/` namespace where the reasoner's output lives. The `nothing imports the derived namespace` test went red on the exact commit that broke it. The reasoner's output tier is supposed to be a dead-end sink — data flows *in*, nothing flows back *out* into the store — and for one commit I'd opened a path. A comment would have shrugged. The BFS didn't. The fix was to keep the gate as a CI-only check instead of a runtime import, and the fence held.

That's the whole thesis in one anecdote: I am not disciplined enough to keep this boundary by hand, and I don't have to be.

---

## 2. Going wide without manufacturing findings

Standpoint tests ~2,000 ports for a throughput anomaly. Test two thousand series for a 3-sigma event and *pure noise alone* hands you about five "discoveries" that mean nothing — and if I print them as flags, I'm lying with statistics while feeling rigorous.

The honest move is to control the false-discovery rate across the whole family at once. One Benjamini-Hochberg pass, one declared budget *q*, and a companion line I can put on the page without flinching: **"tested N, expect ≤ k of these are noise."** That second number isn't decoration; it's `q · n_significant`, computed in the same function that decides what survives.

```python
keep, res = control_z(zscores, q=0.10)
# "flagged 31 of 2065, expect <= 3.1 to be noise"
```

Because it's pure and deterministic, *"pure noise yields ~0 findings"* stops being a hope and becomes a unit test: feed it a spread of noise z-scores, assert nothing survives. Going wide is now safe by construction, not by vigilance.

---

## 3. A feed that rots loudly instead of silently

Every upstream source I don't control can change its schema, go empty, or quietly disappear. The dangerous failure isn't a crash — a crash I'd see. It's a feed that still returns *valid JSON* with a renamed field or zero rows, so the artifact ships looking fine while a whole layer has gone dark.

So each feed has a **contract** — required keys, the items array and the keys each item carries, a liveness floor — checked both against committed fixtures (a producer that drifts fails review) and against freshly-fetched data (a drifted feed fails the *run*, never the user). A contract asserts shape and liveness, never that a value is *correct* — but "the storm feed came back empty and we noticed in CI instead of on the globe" is most of the battle.

---

## 4. Don't let the prose assert a cause

The signature sin of an "honest" data product is the sentence that recasts a co-occurrence as causation — *"port stress rose, **caused by** the storm"* — or a measurement as a forecast. I render plain-English briefs everywhere a number appears, so the prose is exactly where the discipline is easiest to lose.

The cheap fix is real: scan generated copy against a banned lexicon — `caused by`, `due to`, `forecast`, `predict`, `surge in`, `amid escalating` — and fail the build on a hit. It's blunt, and that's the point. It forces every sentence into the only honest shape: *here is a cited number, here is its date, here is a possibly-related thing nearby* — full stop, no story.

---

## The hard case: designing for an LLM in the loop without putting it in the number path

Then I added a reasoner — a step that writes a short situational briefing over the day's measured signals. This is where most "AI-native" products quietly betray the whole premise, because the easy way is to hand the figures to a model and let it write, and now a model that paraphrases a number can misstate one.

Two structural moves keep it honest.

**The number never passes through the model — in fact, today there is no model in the loop at all.** The reasoner that runs over the data is deterministic Python with fixed phrasing templates, *offline*, at build time — it doesn't sit behind a runtime API the site calls, and it doesn't get to invent a figure. Selection, grounding, the statistics, even the phrasing: all deterministic. The only seat a model could ever occupy here is *phrasing* a claim that was already built and already grounded — and the gates below were built for exactly that occupant before deciding it wasn't yet worth the seat. A `Claim` with no citations is **unconstructable** — the type raises in `__post_init__` if you try — so "an ungrounded sentence" isn't a bug to catch, it's a state that can't exist.

**The output is gated, fail-closed.** Before any briefing ships, a gate runs a conjunction: every number in the prose must be *entailed* by a cited source (string-decidable, no LLM judge grading its own homework), a bait battery of questions-with-no-honest-answer must all abstain, and no claim may cite a telemetry field. If any clause fails, the briefing doesn't ship — the build does not "degrade gracefully" into a confident wrong answer. It stops.

The cleanest demonstration I have is a contrast I left in the product on purpose. A cargo brand's marketing once claimed "99.7%" of something. Standpoint carries that as a row tagged `method=external_claim` — *their* number, cited to *them* — sitting next to the value the system actually measured. Same screen, two provenances, clearly labeled. The honest answer to "is that 99.7% true?" is "that's their claim, here's ours," and the system is built so it *cannot* collapse the two into one confident sentence.

---

## Why bother making it mechanical

Because the alternative is vigilance, and vigilance doesn't scale past one tired person. Every one of these checks exists because the honest version and the dishonest version of the code look *almost identical* — one import, one missing FDR pass, one word, one paraphrase — and the difference is invisible in review and catastrophic to a product whose only asset is that you can trust the number.

Making honesty a compile error means the boundary survives me. It survives the rushed Friday commit. It survives the contributor who's never read the design doc. The machine that builds the thing also refuses to build a dishonest version of it.

I pulled the four checks out into a standalone, dependency-free library — **[honesty-harness](https://github.com/joshs444/honesty-harness)** (MIT) — so you can drop them into your own project: the import-graph firewall, the FDR control, the data contracts, the causal/forecast lexicon. Four files, pure stdlib, each a predicate you call from a test you already have. The runnable toy example is a three-module package where a clean context layer reaches nothing quarantined and a malicious one gets caught — the whole pitch, as a passing and a failing assertion.

See the discipline in production on the globe: **[Standpoint](https://joshs444.github.io/freight-radar/)**.

— Josh
