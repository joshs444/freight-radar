import type { LayerId, LayerVisibility, Ships, NewsGeo } from '../types.ts';
import { NEWS_CATEGORIES, rgbCss } from '../lib/colors.ts';

// The globe layer control + key. Layers are grouped into FREIGHT (the measured spine —
// the only layers that carry a computed number) and CONTEXT (cited public data shown as
// a possibly-related signal, never a stated cause). The category boundary itself is part
// of the honesty rail, reinforced by the caption + the persistent provenance footer.

type Row = { id: LayerId; label: string; sw: string };

const SECTIONS: { title: string; caption?: string; rows: Row[] }[] = [
  {
    title: 'Freight',
    rows: [
      { id: 'flags', label: 'flagged', sw: 'pulse' },
      { id: 'chokepoints', label: 'chokepoints', sw: 'amber' },
      { id: 'ports', label: 'ports', sw: 'port' },
      { id: 'ships', label: 'vessels', sw: 'ship' },
      { id: 'lanes', label: 'lanes', sw: 'lane' },
    ],
  },
  {
    title: 'Context',
    caption: 'possibly-related context, not a stated cause',
    rows: [
      { id: 'news', label: 'news', sw: 'news' },
      { id: 'storms', label: 'storms', sw: 'storm' },
      { id: 'wind', label: 'wind', sw: 'wind' },
      { id: 'satellite', label: 'satellite', sw: 'sat' },
    ],
  },
];

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
}

export default function LayerPanel({
  layers,
  onToggle,
  counts,
  ships,
  shipCoverage,
  hasWind,
  newsGeo,
}: LayerPanelProps) {
  const portsN = counts.ports ?? 0;
  const visible = (r: Row): boolean => {
    if (r.id === 'wind') return hasWind;
    if (r.id === 'storms') return (counts.storms ?? 0) > 0;
    if (r.id === 'ships') return (ships?.count ?? 0) > 0;
    if (r.id === 'news') return (counts.news ?? 0) > 0;
    return true;
  };

  const title = (r: Row, on: boolean): string => {
    if (r.id === 'ships' && ships) return ships.note;
    if (r.id === 'satellite')
      return `Real NASA VIIRS true-color satellite · ${SAT_DATE} (near-real-time)`;
    if (r.id === 'news')
      return newsGeo
        ? `Geo-tagged GDELT news coverage · ${newsGeo.window} window · click a dot to read the source`
        : 'Geo-tagged GDELT news coverage';
    return `${on ? 'Hide' : 'Show'} the ${r.label} layer`;
  };

  return (
    <div className="fr-layers" aria-label="Map layers">
      <div className="fr-layers-head">Layers</div>

      {SECTIONS.map((section) => {
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

      <p className="fr-layers-foot">
        Every number computed in Python from cited public data · context is possibly-related, never
        a stated cause · no forecasts.
      </p>
    </div>
  );
}
