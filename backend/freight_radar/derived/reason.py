"""derived/reason.py — the DERIVED reasoner (Step 8, built LAST).

It does the SMALL, honest amount the architecture allows (the cargo-cult critic won this
argument): READ the published store, SELECT a fixed set of this-week facts, GROUND each through
``ground_or_abstain`` (drop anything the store can't cite), phrase with a FIXED template (the
only authoring — no model ever invents a number), and GATE the result fail-closed before it is
written. Every value is read live, so the briefing is always current and always *entailed*.

It runs OFFLINE (a ``python -m`` step, zero runtime LLM cost) — the static site only serves the
artifact. It lives in derived/ (quarantined): nothing in the fact path imports it; refresh.yml
runs it as a subprocess, never a Python import, so the AI firewall holds.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .. import store
from ..honesty.lexicon import scan as scan_causal
from ..registry.layers import REGISTRY
from .contract import ABSTAIN, ground_or_abstain
from .gate import gate_briefing


class DerivedGateBlocked(RuntimeError):
    """The produced briefing failed its own honesty gate — it is never written (fail-closed)."""


def _payload(stem: str, out_dir):
    try:
        return store.get_layer(stem, out_dir=out_dir).get("payload")
    except Exception:  # noqa: BLE001
        return None


def _clean_source(s: object) -> str | None:
    """A news source usable inside a gated claim: a non-empty name with no digit (a stray
    number would fail the attribution gate) and no causal/forecast token (the language firewall)."""
    name = str(s or "").strip()
    if not name or any(ch.isdigit() for ch in name) or scan_causal(name):
        return None
    return name


def _connections(flags: list, news: object, k: int = 3) -> list[tuple[str, list[str]]]:
    """The honest synthesis step: CONNECT each top measured disruption to the world events that
    co-occur with it — strictly the news ALREADY retrieved per flag, as association, never a cause.

    Every number stays entailed: the pct is read from ``flags``; the article count is the length
    of that flag's own list inside the ``news`` layer (``_collect`` recurses into it). The model
    authors no figure — it only joins a measured number to its cited, co-occurring reports.
    """
    items = news.get("items", {}) if isinstance(news, dict) else {}
    ranked = sorted(
        (f for f in flags
         if isinstance(items.get(f.get("flag_id")), dict) and items[f["flag_id"]].get("items")),
        key=lambda f: -(f.get("severity") or 0),
    )
    out: list[tuple[str, list[str]]] = []
    for f in ranked[:k]:
        arts = items[f["flag_id"]]["items"]
        srcs: list[str] = []
        for a in arts:
            name = _clean_source(a.get("source"))
            if name and name not in srcs:
                srcs.append(name)
        if len(srcs) < 2 or f.get("pct_change") is None:
            continue
        word = "transit" if str(f.get("kind", "")).startswith("chokepoint") else "activity"
        named = ", ".join(srcs[:3])
        out.append((
            f"{f['entity']} {word} change of {f['pct_change']}% (measured) co-occurs this week with "
            f"{len(arts)} cited news reports ({named}, …) — possibly-related context, never a stated cause.",
            ["flags", "news"],
        ))
    return out


def build(out_dir) -> dict:
    claims: list[dict] = []

    def add(text: str, cites: list[str]) -> None:
        c = ground_or_abstain(text, cites, out_dir=out_dir)  # drops if any cite can't ground
        if c is not ABSTAIN:
            claims.append({"text": c.text, "cites": list(c.cites)})

    stress = _payload("stress", out_dir)
    as_of = ""
    if isinstance(stress, dict) and stress.get("index") is not None:
        as_of = stress.get("as_of") or ""
        add(
            f"The Global Ocean Freight Stress Index reads {stress['index']} "
            f"(label: {stress.get('label')}) as of {as_of}.",
            ["stress"],
        )

    flags = _payload("flags", out_dir)
    if isinstance(flags, list) and flags:
        add(f"{len(flags)} ports and chokepoints carry an FDR-significant disruption flag this week.", ["flags"])
        hz = next((f for f in flags if "Hormuz" in str(f.get("entity", ""))), None)
        if hz and hz.get("pct_change") is not None:
            add(
                f"Among the flagged, {hz['entity']} shows a transit change of "
                f"{hz['pct_change']}% versus its baseline — a measured reading, never a stated cause.",
                ["flags"],
            )

        # The synthesis: connect the top measured disruptions to their co-occurring CITED news.
        # This is the honest answer to "should the AI do research?" — the research (retrieval) is
        # the deterministic per-flag news join; the AI only joins the measured number to those
        # already-cited reports, as association. Each is grounded + gated like any other claim.
        news = _payload("news", out_dir)
        for text, cites in _connections(flags, news):
            add(text, cites)

    fr = _payload("freight_rate", out_dir)
    if isinstance(fr, dict) and fr.get("items"):
        top = max(fr["items"], key=lambda i: abs(i.get("our_zscore") or 0))
        if top.get("our_zscore") is not None:
            add(
                f"Our freight-cost signal flags the {top['name']} at a {top['our_zscore']:+g} "
                "z-score — an anomaly we computed, association only.",
                ["freight_rate"],
            )

    gat = _payload("gatun", out_dir)
    if isinstance(gat, dict) and gat.get("current_level_ft") is not None:
        add(
            f"At the Panama Canal, the Gatun lake level reads {gat['current_level_ft']} ft, "
            f"in the {gat.get('pctile_alltime')}th percentile all-time.",
            ["gatun"],
        )

    quakes, eonet = _payload("quakes", out_dir), _payload("eonet", out_dir)
    if isinstance(quakes, dict) and isinstance(eonet, dict):
        add(
            f"Cited context this week: {len(quakes.get('items', []))} USGS earthquakes and "
            f"{len(eonet.get('items', []))} NASA EONET natural events near the chain.",
            ["quakes", "eonet"],
        )

    return {
        "tier": "DERIVED",
        "metric": None,
        "agent_model": "claude (offline reasoner — the static site only serves this artifact)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": as_of,
        "method": (
            "An offline agent reads the published store, grounds every claim through verify(), "
            "and the briefing is gate-validated (attribution + abstention + the language "
            "firewall) before it ships. No model is in the number path."
        ),
        "disclaimer": (
            "DERIVED — what an AI said about the cited facts. Every claim traces to a layer; "
            "co-occurrence is association, never causation."
        ),
        "claims": claims,
    }


def write(out_dir) -> Path:
    """Build, GATE fail-closed, then write ai_briefing.json. Raises rather than ship an
    ungated briefing — the reasoner is guilty until the gate proves it innocent."""
    out_dir = Path(out_dir)
    briefing = build(out_dir)
    violations = gate_briefing(briefing, {d.id for d in REGISTRY}, out_dir=out_dir)
    if violations:
        raise DerivedGateBlocked(f"the reasoner's briefing failed its honesty gate: {violations}")
    pth = out_dir / "ai_briefing.json"
    pth.write_text(json.dumps(briefing, indent=2) + "\n")
    return pth


def main(argv: list[str] | None = None) -> int:
    import sys

    from ..config import publish_dir

    args = argv if argv is not None else sys.argv[1:]
    out = Path(args[0]) if args else publish_dir()
    try:
        p = write(out)
        b = json.loads(p.read_text())
        print(f"reasoner: {len(b['claims'])} grounded claims, gate clean -> {p}")
        return 0
    except DerivedGateBlocked as e:
        print(f"reasoner BLOCKED (fail-closed): {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
