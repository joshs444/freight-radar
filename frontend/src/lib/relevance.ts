// Just the fields the score reads — so both a full Flag and the slimmer scrub-replay
// TimeseriesFlag satisfy it without a cast (missing fields simply read as 0/absent).
interface Scoreable {
  kind: string;
  baseline?: number;
  pct_change?: number;
  zscore?: number;
  business?: { lane_count?: number } | null;
  live_storm?: unknown;
  official_event?: unknown;
}

// The honest triage the old "severity" (a raw z-score) lacked. A flag's relevance is
// importance × magnitude × corroboration, each in [0,1]:
//   importance    chokepoints are always strategic (1.0); a port scales by its real
//                 daily traffic — a 0.04-vessel/day terminal is ~0, a 15+/day port ~1.
//   magnitude     the larger of normalized |pct vs norm| and normalized |z|, capped.
//   corroboration a second real-world source (trade lanes exposed, a live storm, an
//                 official event) lifts it to 1.0; an uncorroborated stat blip floors at 0.4.
// So a "+13% on a near-empty port, nothing else" scores ~0 and a "Hormuz −92%, 2 lanes
// exposed" scores ~0.9. The feed + globe default to relevance ≥ FLOOR; everything else is
// one click ("show all") away — cut from the default surface, never from the dataset.

export const RELEVANCE_FLOOR = 0.15;

const VESSEL_FLOOR = 15; // a port at ≥15 vessels/day reads as "matters"

export function flagRelevance(f: Scoreable): number {
  // A chokepoint vessel-size-shift stashes tonnage (DWT) in `baseline`, not vessels/day —
  // the chokepoint branch (importance 1) avoids ever normalizing tonnage as a vessel count.
  const importance = f.kind.startsWith('chokepoint')
    ? 1
    : Math.min(Math.max(f.baseline || 0, 0) / VESSEL_FLOOR, 1);
  const magnitude = Math.min(
    Math.max(Math.abs(f.pct_change || 0) / 100, Math.abs(f.zscore || 0) / 8),
    1
  );
  const corroborated =
    (f.business?.lane_count ?? 0) > 0 || Boolean(f.live_storm) || Boolean(f.official_event);
  return importance * magnitude * (corroborated ? 1 : 0.4);
}

export const isSignalFlag = (f: Scoreable): boolean => flagRelevance(f) >= RELEVANCE_FLOOR;
