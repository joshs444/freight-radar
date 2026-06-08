import { useCatalog, effectiveSource } from '../lib/catalog.ts';
import { Sparkline } from './Sparkline.tsx';

// The ONE provenance primitive: click any datapoint -> see its raw input -> the computation we ran
// -> the published number -> the cited source (linked, licensed, dated). Rendered identically on
// flags, the cross-domain signals, unflagged ports/chokepoints, globe context dots, and the brief —
// "honest provenance at the point, everywhere" as a single invariant fed from the registry catalog.
//
// Two ways to feed it, composable:
//   • explicit props (flags + signals already carry source/source_url/license on the record), or
//   • a layerId — Trace resolves the cited root source + the per-layer tier from catalog.json
//     (effectiveSource), so a port or a quake dot traces without the record carrying provenance.
// Explicit props always win; the catalog only fills the gaps. The honest fences are structural:
// RAW (cited) and COMPUTED-BY-US are separate steps (never collapsed — fence #5), and a `fenced`
// marker renders the "system context — not this place" band national signals require.

interface TraceProps {
  layerId?: string; // resolve cited root source + tier from catalog when props are absent
  tier?: string; // explicit tier label (overrides the catalog's)
  raw?: string; // the cited input series / index
  method?: string; // the computation WE ran (fence #5: never attributed to the source)
  published?: string; // the resulting number, as published
  source?: string; // cited source name (clean label)
  sourceUrl?: string | null; // canonical home of the cited series
  license?: string | null;
  asOf?: string;
  metric?: string; // the owned statistic, when there's no distinct published string
  series?: number[]; // a computed track to sparkline (e.g. a signal's 36-mo z-series)
  seriesUp?: boolean; // colour hint for the sparkline
  honestyNote?: string;
  fenced?: string | null; // 'national' -> render the place-INVARIANT system-context fence
  compact?: boolean; // drop the tier badge (when the caller already shows it)
}

export default function Trace(props: TraceProps) {
  const catalog = useCatalog();
  const eff = props.layerId ? effectiveSource(catalog, props.layerId) : null;

  const source = props.source ?? eff?.source?.name ?? null;
  const sourceUrl = props.sourceUrl ?? eff?.source?.url ?? null;
  const license = props.license ?? eff?.source?.license ?? null;
  const tierLabel = props.tier ?? eff?.tier?.label ?? null;
  const tierCls = eff?.tier?.cls ?? '';
  const honestyNote = props.honestyNote ?? eff?.honestyNote ?? null;
  const raw = props.raw ?? props.metric ?? eff?.metric ?? null;

  return (
    <div className="fr-trace">
      {!props.compact && tierLabel && (
        <span className={`fr-trace-tier ${tierCls}`}>{tierLabel}</span>
      )}
      {props.fenced === 'national' && (
        <span className="fr-trace-fence">system context — national / global, not this place</span>
      )}
      <ol className="fr-trace-chain">
        {raw && (
          <li className="fr-trace-step">
            <span className="fr-trace-k">raw</span>
            <span className="fr-trace-v">{raw}</span>
          </li>
        )}
        {props.method && (
          <li className="fr-trace-step">
            <span className="fr-trace-k">computed by us</span>
            <span className="fr-trace-v">{props.method}</span>
          </li>
        )}
        {props.published && (
          <li className="fr-trace-step">
            <span className="fr-trace-k">published</span>
            <span className="fr-trace-v">{props.published}</span>
          </li>
        )}
        <li className="fr-trace-step">
          <span className="fr-trace-k">source</span>
          <span className="fr-trace-v">
            {source ? (
              sourceUrl ? (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="fr-trace-src"
                >
                  {source} ↗
                </a>
              ) : (
                <b>{source}</b>
              )
            ) : (
              <span className="fr-trace-muted">cited source</span>
            )}
            {license ? <span className="fr-trace-lic"> · {license}</span> : null}
            {props.asOf ? <span className="fr-trace-as"> · as of {props.asOf}</span> : null}
          </span>
        </li>
      </ol>
      {props.series && props.series.length >= 2 && (
        <div className="fr-trace-spark">
          <Sparkline
            values={props.series}
            width={132}
            height={26}
            color={props.seriesUp ? '#b0521e' : '#2f6f8f'}
          />
          <span className="fr-trace-spark-cap">computed track</span>
        </div>
      )}
      {honestyNote && <p className="fr-trace-note">{honestyNote}</p>}
    </div>
  );
}
