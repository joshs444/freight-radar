"""The one field-spec grammar — the single source the data contracts (and the frontend
TS interfaces) are DERIVED from, keyed by sidecar stem.

A sidecar's shape used to live twice: once as a hand-written ``Contract`` in
``contracts.py`` (the backend drift floor) and once as a hand-written ``interface`` in
``frontend/src/types.ts`` (the reader's view). Two hand-maintained mirrors of the same
JSON inevitably drift. This module is the SSOT they both reduce from: a deliberately
tiny typed grammar (the ``_Field`` constructors below, capped) describes each sidecar,
and ``contracts.py`` derives ``SIDECAR_CONTRACTS`` from it (a migration test proves the
derived dict equals the old literals byte-for-byte before they were deleted).

The grammar is the FLOOR, never the whole truth: a ``Shape`` carries the full field set
(so a TS renderer can emit the interface) AND a ``contract`` descriptor naming the
SUBSET the drift detector actually gates on — flags has ~20 fields but its contract floor
is the four geo/identity keys Globe.tsx reads, so a non-load-bearing field can be added
without re-blessing a contract. Two renderers, one source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# --- the tiny typed field grammar (8 constructors, capped) -------------------
# Each is a frozen dataclass so a Shape is a plain, hashable description. `ts` on each
# returns the TypeScript type it renders to (deliverable 4); the contract derivation only
# needs the structure (which fields exist, which are optional, which lists are items).
@dataclass(frozen=True)
class _Field:
    """Base — every grammar node renders to one TS type."""

    def ts(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass(frozen=True)
class STR(_Field):
    def ts(self) -> str:
        return "string"


@dataclass(frozen=True)
class NUM(_Field):
    def ts(self) -> str:
        return "number"


@dataclass(frozen=True)
class BOOL(_Field):
    def ts(self) -> str:
        return "boolean"


@dataclass(frozen=True)
class OPT(_Field):
    """A non-required field. Two independent axes (both default True — the common case):
    `key_optional` renders the `?` (the key may be absent) and marks it NOT contract-required;
    `nullable` renders `| null` (the value may be null). A nullable-but-always-present field
    (e.g. `country: string | null`) is OPT(STR(), key_optional=False) — a present, required key
    whose value can be null. `?`-rendering uses `is_opt_key` so the contract floor stays exact."""

    inner: _Field
    key_optional: bool = True
    nullable: bool = True

    def ts(self) -> str:
        return f"{self.inner.ts()} | null" if self.nullable else self.inner.ts()


@dataclass(frozen=True)
class LIST(_Field):
    """A homogeneous JSON array."""

    inner: _Field

    def ts(self) -> str:
        t = self.inner.ts()
        return f"{t}[]" if " " not in t else f"({t})[]"


@dataclass(frozen=True)
class RECORD(_Field):
    """A `Record<string, valtype>` (an object keyed by id, not a fixed-field struct)."""

    val: _Field

    def ts(self) -> str:
        return f"Record<string, {self.val.ts()}>"


@dataclass(frozen=True)
class REF(_Field):
    """A reference to a named OBJ defined in the same registry (renders as the interface
    name in TS, e.g. `CargoMix`)."""

    name: str

    def ts(self) -> str:
        return self.name


@dataclass(frozen=True)
class RAW(_Field):
    """Escape hatch: an exotic TS type the capped grammar shouldn't grow a constructor for
    (a tuple `[number, number]`, an inline object, a union). The contract treats it as a
    present scalar; the TS renderer emits the literal string verbatim."""

    type_str: str

    def ts(self) -> str:
        return self.type_str


# --- a named object shape (becomes a TS interface; defines item_requires) ----
def is_opt_key(typ: _Field) -> bool:
    """True for a field whose KEY may be absent (renders `?`, not contract-required). A
    nullable-but-present field — OPT(..., key_optional=False) — returns False."""
    return isinstance(typ, OPT) and typ.key_optional


@dataclass(frozen=True)
class OBJ:
    """A fixed-field object. `name` is the TS interface name. `fields` is ordered
    (name -> grammar node). A field whose key may be absent is non-required (see is_opt_key)."""

    name: str
    fields: tuple[tuple[str, _Field], ...]

    def required_keys(self) -> list[str]:
        return [k for k, t in self.fields if not is_opt_key(t)]


# --- the contract floor a shape exposes to the drift detector ---------------
@dataclass(frozen=True)
class ContractSpec:
    """The SUBSET of a shape the drift detector gates on (reduces to a `Contract`):
    `requires` top-level keys, the `items_key` array + its `item_requires` keys, the
    `min_items` liveness floor, `is_array` (a top-level JSON array), `nonempty_lists`.
    Omitted lists default to the empty floor — a contract is a floor, never a forecast."""

    requires: tuple[str, ...] = ()
    items_key: Optional[str] = None
    item_requires: tuple[str, ...] = ()
    min_items: int = 0
    is_array: bool = False
    nonempty_lists: tuple[str, ...] = ()


# --- a sidecar's full shape: its fields (for TS) + its contract floor --------
@dataclass(frozen=True)
class Shape:
    """One sidecar's shape, keyed by stem in SHAPES below.

    `root` is the top-level structure: an OBJ (a JSON object sidecar) or a LIST(REF(...))
    (a top-level JSON array sidecar like lanes/flags). `objs` are the named nested object
    shapes it references (each becomes a TS interface). `contract` is the drift floor.
    `ts_root` names the top-level interface (defaults to the root OBJ's name).
    `gen` marks a shape whose TS interface is GENERATED into types.gen.ts (deliverable 4):
    only the mechanical, comment-free CONTEXT shapes set it; spine/exotic interfaces with
    hand-written doc comments stay authored in types.ts and leave it False."""

    root: object  # OBJ | LIST
    contract: ContractSpec
    objs: tuple[OBJ, ...] = field(default_factory=tuple)
    ts_root: Optional[str] = None
    gen: bool = False


# shared item shape referenced by the per-family signal stems
_SIGNAL_ITEM = OBJ(
    "SignalItem",
    (
        ("family", STR()),
        ("id", STR()),
        ("name", STR()),
        ("unit", STR()),
        ("as_of", STR()),
        ("value", NUM()),
        ("our_zscore", NUM()),
        ("fdr_significant", BOOL()),
        ("source", STR()),
        ("source_url", STR()),
        ("method", STR()),
        ("z_series", LIST(REF("SignalZPoint"))),
        ("fenced", STR()),
    ),
)

# the per-family FRED-z signal stems share one shape: an items array where each row owns a
# z-score + its FDR verdict. The contract floor is the fields the store + ledger read.
_SIGNAL_SHAPE = Shape(
    root=OBJ(
        "Signal",
        (
            ("generated_at", STR()),
            ("source", STR()),
            ("source_url", STR()),
            ("method", STR()),
            ("counts", RAW("{ tested: number; significant: number }")),
            ("items", LIST(REF("SignalItem"))),
        ),
    ),
    objs=(_SIGNAL_ITEM,),
    contract=ContractSpec(
        requires=("counts", "generated_at", "items", "method", "source", "source_url"),
        items_key="items",
        item_requires=("fdr_significant", "id", "name", "our_zscore"),
        min_items=1,
    ),
)


# ============================================================================
# THE REGISTRY — one Shape per contracted sidecar stem. Order mirrors contracts.py's
# old literal order so the migration diff (derived == old literals) reads cleanly.
# ============================================================================
SHAPES: dict[str, Shape] = {
    # --- the measured spine (core) ---
    "snapshot": Shape(
        root=OBJ(
            "Snapshot",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("source", STR()),
                ("chokepoints", LIST(REF("SnapshotChokepoint"))),
                ("ports", LIST(REF("SnapshotPort"))),
            ),
        ),
        contract=ContractSpec(
            requires=("as_of", "chokepoints", "generated_at", "ports", "source"),
            nonempty_lists=("chokepoints", "ports"),
        ),
    ),
    "lanes": Shape(
        root=LIST(REF("Lane")),
        ts_root="Lane",
        contract=ContractSpec(
            is_array=True,
            item_requires=("from", "intensity", "to"),
            min_items=1,
        ),
    ),
    "flags": Shape(
        root=LIST(REF("Flag")),
        ts_root="Flag",
        contract=ContractSpec(
            is_array=True,
            item_requires=("entity", "flag_id", "portid", "severity"),
            min_items=0,  # a calm day can carry zero flags
        ),
    ),
    # --- cited context ring (the globe dot layers) ---
    # These seven are GENERATED into types.gen.ts (gen=True): mechanical, comment-free shapes
    # whose interface is a pure reduction of the fields below. News_geo stays hand-written
    # (it carries field-level doc comments the capped grammar shouldn't encode).
    "quakes": Shape(
        gen=True,
        root=OBJ(
            "Quakes",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("source", STR()),
                ("source_url", STR()),
                ("disclaimer", STR()),
                ("min_mag", NUM()),
                ("counts", RAW("{ total: number; m5plus: number }")),
                ("items", LIST(REF("QuakeItem"))),
            ),
        ),
        objs=(
            OBJ(
                "QuakeItem",
                (
                    ("id", STR()),
                    ("mag", NUM()),
                    ("place", STR()),
                    ("lat", NUM()),
                    ("lon", NUM()),
                    ("depth_km", OPT(NUM(), key_optional=False)),
                    ("time", STR()),
                    ("tsunami", BOOL()),
                    ("url", STR()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=("generated_at", "items", "source", "source_url"),
            items_key="items",
            item_requires=("id", "lat", "lon", "mag", "place", "url"),
            min_items=1,
        ),
    ),
    "news_geo": Shape(
        root=OBJ("NewsGeo", ()),
        contract=ContractSpec(
            requires=("generated_at", "items", "source", "source_url"),
            items_key="items",
            item_requires=("category", "lat", "lon", "url"),
            min_items=1,
        ),
    ),
    "eonet": Shape(
        gen=True,
        root=OBJ(
            "Eonet",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("source", STR()),
                ("source_url", STR()),
                ("disclaimer", STR()),
                ("counts", RAW("{ events: number; by_category: Record<string, number> }")),
                ("items", LIST(REF("EonetItem"))),
            ),
        ),
        objs=(
            OBJ(
                "EonetItem",
                (
                    ("id", STR()),
                    ("title", STR()),
                    ("category", STR()),
                    ("lat", NUM()),
                    ("lon", NUM()),
                    ("date", STR()),
                    ("url", STR()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=("generated_at", "items", "source", "source_url"),
            items_key="items",
            item_requires=("category", "id", "lat", "lon", "title", "url"),
            min_items=1,
        ),
    ),
    "marine": Shape(
        gen=True,
        root=OBJ(
            "Marine",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("source", STR()),
                ("source_url", STR()),
                ("disclaimer", STR()),
                ("counts", RAW("{ chokepoints: number }")),
                ("items", LIST(REF("MarineItem"))),
            ),
        ),
        objs=(
            OBJ(
                "MarineItem",
                (
                    ("name", STR()),
                    ("lat", NUM()),
                    ("lon", NUM()),
                    ("wave_height_m", NUM()),
                    ("wave_period_s", OPT(NUM(), key_optional=False)),
                    ("observed_at", STR()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=("generated_at", "items", "source", "source_url"),
            items_key="items",
            item_requires=("lat", "lon", "name", "observed_at", "wave_height_m"),
            min_items=1,
        ),
    ),
    "tides": Shape(
        gen=True,
        root=OBJ(
            "Tides",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("source", STR()),
                ("source_url", STR()),
                ("disclaimer", STR()),
                ("counts", RAW("{ ports: number }")),
                ("items", LIST(REF("TideItem"))),
            ),
        ),
        objs=(
            OBJ(
                "TideItem",
                (
                    ("port", STR()),
                    ("station", STR()),
                    ("lat", NUM()),
                    ("lon", NUM()),
                    ("water_level_ft", NUM()),
                    ("observed_at", STR()),
                    ("url", STR()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=("generated_at", "items", "source", "source_url"),
            items_key="items",
            item_requires=("lat", "lon", "observed_at", "port", "url", "water_level_ft"),
            min_items=1,
        ),
    ),
    "streamflow": Shape(
        gen=True,
        root=OBJ(
            "Streamflow",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("source", STR()),
                ("source_url", STR()),
                ("disclaimer", STR()),
                ("counts", RAW("{ gauges: number }")),
                ("items", LIST(REF("StreamflowItem"))),
            ),
        ),
        objs=(
            OBJ(
                "StreamflowItem",
                (
                    ("site", STR()),
                    ("river", STR()),
                    ("place", STR()),
                    ("lat", NUM()),
                    ("lon", NUM()),
                    ("stage_ft", NUM()),
                    ("observed_at", STR()),
                    ("url", STR()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=("generated_at", "items", "source", "source_url"),
            items_key="items",
            item_requires=("lat", "lon", "river", "site", "stage_ft", "url"),
            min_items=1,
        ),
    ),
    "disruptions": Shape(
        gen=True,
        root=OBJ(
            "Disruptions",
            (
                ("generated_at", STR()),
                ("as_of", STR()),
                ("window_days", NUM()),
                ("source", STR()),
                ("source_url", STR()),
                ("events", LIST(REF("DisruptionEvent"))),
                ("counts", RAW("{ events: number; red: number; flags_corroborated: number }")),
            ),
        ),
        objs=(
            OBJ(
                "DisruptionEvent",
                (
                    ("eventid", NUM()),
                    ("type", STR()),
                    ("type_label", STR()),
                    ("name", STR()),
                    ("alertlevel", STR()),
                    ("country", STR()),
                    ("from", STR()),
                    ("to", STR()),
                    ("lat", NUM()),
                    ("lon", NUM()),
                    ("severity", STR()),
                    ("affected_ports", RAW("{ portid: string; name: string }[]")),
                    ("n_affected_ports", NUM()),
                    ("near_chokepoints", RAW("{ portid: string; name: string; km: number }[]")),
                    ("affected_population", STR()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=("events", "generated_at", "source", "source_url"),
            items_key="events",
            item_requires=("alertlevel", "eventid", "lat", "lon", "name", "type"),
            min_items=0,  # GDACS can be quiet over the trailing window
        ),
    ),
    "gatun": Shape(
        gen=True,
        root=OBJ(
            "Gatun",
            (
                ("available", BOOL()),
                ("portid", STR()),
                ("name", STR()),
                ("as_of", STR()),
                ("current_level_ft", NUM()),
                ("pctile_alltime", NUM()),
                ("change_30d_ft", NUM()),
                ("change_365d_ft", NUM()),
                ("level_spark", LIST(NUM())),
                ("normal_max_draft_ft", NUM()),
                ("min_projected_neopanamax_draft_ft", NUM()),
                ("draft_restricted", BOOL()),
                ("surcharge_pct_now", NUM()),
                ("projection", LIST(REF("GatunProjection"))),
                ("source", STR()),
                ("source_url", STR()),
                ("disclaimer", STR()),
                ("lat", NUM()),
                ("lon", NUM()),
                ("generated_at", STR()),
            ),
        ),
        objs=(
            OBJ(
                "GatunProjection",
                (
                    ("date", STR()),
                    ("level_ft", NUM()),
                    ("surcharge_pct", NUM()),
                    ("neopanamax_draft_ft", NUM()),
                    ("panamax_draft_ft", NUM()),
                ),
            ),
        ),
        contract=ContractSpec(
            requires=(
                "as_of",
                "available",
                "current_level_ft",
                "generated_at",
                "lat",
                "lon",
                "projection",
            ),
        ),
    ),
    # --- the measured SIGNAL families (one shared shape, FRED-z) ---
    "commodities": _SIGNAL_SHAPE,
    "macro": _SIGNAL_SHAPE,
    "metals": _SIGNAL_SHAPE,
    "freight_rate": _SIGNAL_SHAPE,
    "slack": _SIGNAL_SHAPE,
    "labor": _SIGNAL_SHAPE,
    # --- H1-F: the three previously-uncontracted measured-spine sidecars ---
    # signals_fdr: the POOLED cross-family FDR artifact (signal_pool.py). Distinct from the
    # per-family stems above — it carries no generated_at/source/source_url at the TOP level
    # (provenance lives per item, stamped through the pool); the floor is the trio the Board
    # + headline read (method/counts/items) plus each row's z + its pooled FDR verdict.
    "signals_fdr": Shape(
        root=OBJ("SignalsFdr", ()),
        contract=ContractSpec(
            requires=("counts", "items", "method"),
            items_key="items",
            item_requires=("fdr_significant", "id", "our_zscore"),
            min_items=1,
        ),
    ),
    # timeseries: the per-chokepoint daily track the scrubber replays (CORE — App.tsx blocks
    # the play-through-history view on it). chokepoints now carry normal + cap_normal (H1-C).
    "timeseries": Shape(
        root=OBJ("Timeseries", ()),
        contract=ContractSpec(
            requires=("chokepoints", "dates", "flags", "max_date", "series"),
            items_key="chokepoints",
            item_requires=("cap_normal", "lat", "lon", "name", "normal", "portid", "values"),
            min_items=1,
        ),
    ),
    # stress: the Global Ocean Freight Stress Index (narrative/stress.py) — CORE (the headline
    # + Board read it). A scalar sidecar: the floor is the index + its breadth/depth basis.
    "stress": Shape(
        root=OBJ("Stress", ()),
        contract=ContractSpec(
            requires=(
                "as_of",
                "available",
                "breadth",
                "depth",
                "generated_at",
                "index",
                "label",
                "source",
            ),
        ),
    ),
}


def to_contract_kwargs(stem: str) -> dict:
    """Reduce a stem's Shape to the kwargs for a ``contracts.Contract`` — the contract is
    DERIVED here, never hand-maintained. (Returns plain frozensets/ints the dataclass takes.)"""
    spec = SHAPES[stem].contract
    return {
        "requires": frozenset(spec.requires),
        "items_key": spec.items_key,
        "item_requires": frozenset(spec.item_requires),
        "min_items": spec.min_items,
        "is_array": spec.is_array,
        "nonempty_lists": frozenset(spec.nonempty_lists),
    }
