# Freight Radar

A living dark-globe map of ocean freight: the 28 IMF-tracked maritime chokepoints + top ports
glow by real daily activity, and a durable Temporal agent auto-flags disruptions (chokepoint
transit collapse, port congestion, Cape-of-Good-Hope rerouting) into a severity-ranked
"current issues" rail — each flag a plain-English "what's happening + why" brief.

**Status:** planning → Wave 0. See [PLAN.md](PLAN.md) for the full wave-by-wave build plan,
verified data endpoints, and architecture.

Data: IMF PortWatch (free, no key) for the load-bearing backbone; aisstream live AIS as optional,
non-load-bearing garnish. Daily-granularity, refreshed weekly — the value is the auto-flagging,
not refresh speed.
