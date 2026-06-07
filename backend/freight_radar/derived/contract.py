"""The honest-reasoning contract — the keystone the AI-native chapter binds to (§2b).

Everything reusable lives here, not in a reasoner script: the signals board, the bitemporal
time-travel surface, the hyp_* association tier, and the DERIVED reasoner all emit THESE types
and inherit THIS gate instead of each inventing its own honesty rules. The design move that
makes Standpoint structurally unable to fabricate: a claim is a TYPE that cannot hold an
ungrounded sentence (``Claim`` with empty cites is unconstructable — ``__post_init__`` raises),
and an association is a typed OBJECT, never prose (linting a struct is decidable; linting prose
about two co-moving series is not — and prose is exactly where false causation gets smuggled in).

The single law is ``ground_or_abstain``: it re-verifies every cite against the live store via
``store.verify`` and drops the whole claim on any abstain. The same gate, every pillar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .. import store


@dataclass(frozen=True)
class RetrievedObservation:
    """The ONLY currency reasoning is allowed over — a cited observation with full lineage.

    Constructed only by the retrieval layer (never by a model): the model never sees a raw
    table row, it sees a typed observation it must cite. Mirrors ``fct_observation``'s columns
    so a claim's cite resolves straight back to the bitemporal index.
    """

    entity_key: str
    metric_key: str
    value: object
    method: str
    as_of: Optional[str]
    knowledge_time: Optional[str]
    tier: str
    lineage_run_id: str


@dataclass(frozen=True)
class AssociationObj:
    """A model-found association as a TYPED object, never a sentence. The causal-illusion
    literature shows prose + bar-charts produce the highest false-causation inference, so an
    association is emitted as this struct (a decidable lint) and rendered by a controlled
    component — it is never free text the model wrote. ``confounder_note`` is mandatory and
    non-empty: an association that can't name what might confound it is not admissible."""

    layer_a: str
    layer_b: str
    method: str  # one of: pearson | spearman | lead_lag
    window: str
    confounder_note: str
    lag: int = 0

    def __post_init__(self) -> None:
        if self.method not in ("pearson", "spearman", "lead_lag"):
            raise ValueError(f"AssociationObj.method must be a declared stat, got {self.method!r}")
        if not (self.confounder_note or "").strip():
            raise ValueError("AssociationObj requires a non-empty confounder_note")


@dataclass(frozen=True)
class Claim:
    """A grounded assertion. THE honesty thesis as a type: a claim with zero cites is
    unconstructable — you cannot represent an ungrounded sentence in memory. Each cite is a
    handle the store can resolve back to a real observation (today a layer id; as the
    bitemporal index lands, a ``lineage_run_id``)."""

    text: str
    cites: tuple[str, ...]
    association: Optional[AssociationObj] = None

    def __post_init__(self) -> None:
        if not self.cites:
            raise ValueError("a Claim must cite >=1 observation — an ungrounded claim is unconstructable")
        if not isinstance(self.cites, tuple):
            object.__setattr__(self, "cites", tuple(self.cites))


class _Abstain:
    """The honest 'no' as a singleton — a draft that can't be grounded yields this, never a
    fabricated claim. ``ground_or_abstain`` returns it; callers drop the claim on identity."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "ABSTAIN"

    def __bool__(self) -> bool:
        return False


ABSTAIN = _Abstain()


def ground_or_abstain(text: str, cites, *, association: AssociationObj | None = None, out_dir=None):
    """The single grounding law every pillar shares. Re-verifies EVERY cite against the live
    store (``store.verify``) at emit time; if any cite fails to ground, the whole claim is
    dropped (returns ``ABSTAIN``). Only a fully-grounded draft becomes a ``Claim``. This is the
    function the reasoner, the board, and (eventually) the chat all call — one gate, not four.
    """
    cites = tuple(cites or ())
    if not cites:
        return ABSTAIN
    for cite in cites:
        v = store.verify(cite, out_dir=out_dir)
        if not v.get("grounded"):
            return ABSTAIN
    return Claim(text=text, cites=cites, association=association)
