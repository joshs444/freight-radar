import type { AppView } from '../types.ts';
import type { LayerId, LayerVisibility } from './layers.gen.ts';
import { LAYER_IDS } from './layers.gen.ts';

// A Lens is a named, shareable scene: an exact set of globe layers + a view. It's the
// "recall" half of the navigation model (the ⌘K palette is "discover"). Applying a lens
// sets each layer ON iff it's listed, switches the view, and writes ?lens=<id> to the URL
// so the exact scene is one-click loadable + shareable. A lens never invents data — it's
// just which honest layers you're looking at; Context layers remain cited, never a cause.
export interface Lens {
  id: string;
  name: string;
  blurb: string;
  view: AppView;
  on: LayerId[]; // layers to enable; every other LayerId is turned off
}

export const LENSES: Lens[] = [
  {
    id: 'freight-spine',
    name: 'Freight spine',
    blurb: 'Just the measured chain we own — flagged chokepoints, ports, vessels, lanes.',
    view: 'globe',
    on: ['flags', 'chokepoints', 'ports', 'ships', 'lanes'],
  },
  {
    id: 'storm-watch',
    name: 'Storm watch',
    blurb: 'Active cyclones, GDACS alerts, seas and wind over the freight chain.',
    view: 'globe',
    on: ['flags', 'chokepoints', 'lanes', 'storms', 'hazards', 'marine', 'wind'],
  },
  {
    id: 'hydrology',
    name: 'Hydrology',
    blurb: 'Water levels that set draft windows — tides at ports, river stage inland.',
    view: 'globe',
    on: ['flags', 'chokepoints', 'ports', 'tides', 'streamflow', 'marine'],
  },
  {
    id: 'world-pulse',
    name: 'World pulse',
    blurb: 'Cited world events near the chain — news, quakes, natural events, hazard alerts.',
    view: 'globe',
    on: ['flags', 'chokepoints', 'news', 'quakes', 'eonet', 'hazards'],
  },
  {
    id: 'source-ledger',
    name: 'Source ledger',
    blurb: 'Every layer, tier-stamped with its source, license, and freshness.',
    view: 'ledger',
    on: ['flags', 'chokepoints', 'ports', 'lanes'],
  },
];

export const LENS_BY_ID: Record<string, Lens> = Object.fromEntries(LENSES.map((l) => [l.id, l]));

// Expand a lens's `on` list into a full LayerVisibility map (listed = on, all else off).
export function lensVisibility(lens: Lens): LayerVisibility {
  const on = new Set<LayerId>(lens.on);
  const out = {} as LayerVisibility;
  for (const id of LAYER_IDS) out[id] = on.has(id);
  return out;
}
