"""The shared causal/forecast-verb lexicon — one banned list, scanned everywhere.

The centrum failure mode is asserting that one thing *caused* or *will cause* another.
A context/signal layer's copy may surface a cited fact + its date and STOP — it may
never recast a co-occurrence as causation. This replaces the per-layer verb tuples that
``test_news_geo`` / ``test_quakes`` used to hardcode: the registry honesty suite scans
every layer's copy against THIS list, so a new layer is covered for free.

Scope note: this bans *asserted causation* in a layer's own copy. It is NOT a blanket
"forecast" ban — a layer that IS a cited model forecast (GFS wind) or a measured
projection (Gatún draft) legitimately surfaces a model's own future value (the temporal
model allows "a model's own valid-time"). So the scan targets the context-ring copy +
the registry honesty notes, never the forecast-by-design layers' internals or a
disclaimer that *negates* these words ("no forecasts", "not a stated cause").
"""

from __future__ import annotations

CAUSAL_FORECAST: tuple[str, ...] = (
    "caused by",
    "because of",
    "due to",
    "triggered by",
    "results in",
    "leads to",
    "led to",
    "will disrupt",
    "responsible for",
    "blamed on",
    "sparked by",
    "forecast",
    "predict",
    "cascade",
)


def scan(text: str) -> list[str]:
    """Return the banned phrases present in `text` (case-insensitive)."""
    low = text.lower()
    return [v for v in CAUSAL_FORECAST if v in low]
