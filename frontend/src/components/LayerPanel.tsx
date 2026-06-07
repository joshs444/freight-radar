import type { LayerId, LayerVisibility, Ships, NewsGeo, Quakes } from '../types.ts';
import { NEWS_CATEGORIES, rgbCss } from '../lib/colors.ts';
import { LAYER_SECTIONS, type LayerRow } from '../lib/layers.gen.ts';

// The globe layer control + key. Layers are grouped into FREIGHT (the measured spine —
// the only layers that carry a computed number) and CONTEXT (cited public data shown as
// a possibly-related signal, never a stated cause). The category boundary itself is part
// of the honesty rail, reinforced by the caption + the persistent provenance footer.
// The sections + swatches are GENERATED from the Python registry (layers.gen.ts) so the
// panel can't drift from what the backend actually publishes.

// VIIRS true-color is published ~a day behind; matches Globe's GIBS_DATE (2 days back).
const SAT_DATE = (() => {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 2);
  return d.toISOString().slice(0, 10);
})();

interface LayerPanelProps {
  layers: LayerVisibility;
  onToggle: (id: LayerId) => void;
  counts: Partial<Record<LayerId, number>>;
  ships: Ships | null;
  shipCoverage?: number;
  hasWind: boolean;
  newsGeo: NewsGeo | null;
  quakes: Quakes | null;
  spineFdr?: { tested: number; flagged: number };
}

export default function LayerPanel({
  layers,
  onToggle,
  counts,
  ships,
  shipCoverage,
  hasWind,
  newsGeo,
  quakes,
  spineFdr,
}: LayerPanelProps) {
  const portsN = counts.ports ?? 0;
  const visible = (r: LayerRow): boolean => {
    if (r.id === 'wind') return hasWind;
    if (r.id === 'storms') return (counts.storms ?? 0) > 0;
    if (r.id === 'ships') return (ships?.count ?? 0) > 0;
    if (r.id === 'news') return (counts.news ?? 0) > 0;
    if (r.id === 'quakes') return (counts.quakes ?? 0) > 0;
    return true;
  };

  const title = (r: LayerRow, on: boolean): string => {
    if (r.id === 'ships' && ships) return ships.note;
    if (r.id === 'satellite')
      return `Real NASA VIIRS true-color satellite · ${SAT_DATE} (near-real-time)`;
    if (r.id === 'news')
      return newsGeo
        ? `Geo-tagged GDELT news coverage · ${newsGeo.window} window · click a dot to read the source`
        : 'Geo-tagged GDELT news coverage';
    if (r.id === 'quakes')
      return quakes
        ? `USGS M${quakes.min_mag.toFixed(1)}+ earthquakes, past 7 days · dot size = magnitude · click for the USGS event`
        : 'USGS earthquakes (M4+, past 7 days)';
    return `${on ? 'Hide' : 'Show'} the ${r.label} layer`;
  };

  return (
    <div className="fr-layers" aria-label="Map layers">
      <div className="fr-layers-head">Layers</div>

      {LAYER_SECTIONS.map((section) => {
        const rows = section.rows.filter(visible);
        if (!rows.length) return null;
        return (
          <div className="fr-layers-section" key={section.title}>
            <div className="fr-layers-section-head">{section.title}</div>
            {section.caption && <div className="fr-layers-caption">{section.caption}</div>}
            {rows.map((r) => {
              const on = layers[r.id];
              const n = counts[r.id];
              return (
                <div key={r.id}>
                  <button
                    type="button"
                    className={`fr-layer ${on ? 'on' : 'off'}`}
                    onClick={() => onToggle(r.id)}
                    aria-pressed={on}
                    title={title(r, on)}
                  >
                    <i className={`sw ${r.sw}`} />
                    <span className="fr-layer-label">{r.label}</span>
                    {n != null && r.id !== 'wind' && (
                      <span className="fr-layer-n">{n.toLocaleString()}</span>
                    )}
                    <span className="fr-layer-switch" aria-hidden="true" />
                  </button>

                  {/* news topic key — shows only while the news layer is on */}
                  {r.id === 'news' && on && newsGeo && (
                    <div className="fr-news-key" aria-label="News topics">
                      {NEWS_CATEGORIES.map((c) => {
                        const cn = newsGeo.counts?.[c.key] ?? 0;
                        if (!cn) return null;
                        return (
                          <span className="fr-news-key-row" key={c.key} title={c.label}>
                            <i className="fr-news-dot" style={{ background: rgbCss(c.color) }} />
                            <span className="fr-news-key-lbl">{c.label}</span>
                            <span className="fr-news-key-n">{cn}</span>
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}

      {(ships?.count ?? 0) > 0 && (
        <p className="fr-layers-note">
          Vessels = a point-in-time AIS sample
          {shipCoverage
            ? ` near ${shipCoverage} of the 28 chokepoints right now`
            : ' near the 28 chokepoints'}{' '}
          — not all ships, not the {portsN.toLocaleString()} ports.
        </p>
      )}

      {spineFdr && spineFdr.flagged > 0 && (
        <p className="fr-layers-note">
          Freight spine: ~{spineFdr.tested.toLocaleString()} ports tested · {spineFdr.flagged}{' '}
          flagged · FDR-gated (q=0.10, expect ≤{Math.round(0.1 * spineFdr.flagged)} false). We test
          wide, flag only the genuinely-significant.
        </p>
      )}

      <p className="fr-layers-foot">
        Every number computed in Python from cited public data · context is possibly-related, never
        a stated cause · no forecasts.
      </p>
    </div>
  );
}
