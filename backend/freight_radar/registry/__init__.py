"""The Standpoint layer registry — the single source of truth for every layer.

`layers.py` is authoritative: one `LayerDescriptor` per layer carries its epistemic
tier, its backend producer + pipeline order, the sidecar it writes, and the frontend
toggle/fetch metadata. The three lists that used to drift by hand —
`enrich.ENRICHERS`, `publish._SIDECARS`, and the TS `LayerId` union — are all *derived*
from it (the last via `codegen.py`). Adding a layer is one append here, not a
seven-file two-language hand-edit. See docs/plans/STANDPOINT-VISION.md §4.
"""

from .layers import (  # noqa: F401
    ENRICHERS,
    REGISTRY,
    SIDECARS,
    EnrichCtx,
    Globe,
    Kind,
    LayerDescriptor,
    Producer,
    Source,
    by_id,
    globe_descriptors,
    to_json,
)
