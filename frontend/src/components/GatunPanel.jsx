import { Sparkline } from './Sparkline.jsx';

// Panama Canal Gatun Lake — a LEADING indicator the transit-count data can't give.
// Lake level drives the max transit draft; ACP cuts draft + adds surcharge in
// drought weeks before the PortWatch count falls. Shown on the Panama chokepoint.
export default function GatunPanel({ gatun }) {
  if (!gatun?.available) return null;
  const draftCut = gatun.normal_max_draft_ft - gatun.min_projected_neopanamax_draft_ft;
  const down = (gatun.change_30d_ft || 0) < 0;
  return (
    <div className="fr-gat">
      <div className="fr-gat-head">
        Panama draft · leading indicator <span>· ACP, not PortWatch</span>
      </div>
      <div className="fr-gat-row">
        <div className="fr-gat-stat">
          <b>{gatun.current_level_ft} ft</b>
          <span>Gatun lake level</span>
        </div>
        <div className="fr-gat-stat">
          <b className={down ? 'lo' : ''}>
            {gatun.change_30d_ft > 0 ? '+' : ''}
            {gatun.change_30d_ft} ft
          </b>
          <span>30-day change</span>
        </div>
        <div className="fr-gat-stat">
          <b>{gatun.pctile_alltime}%</b>
          <span>vs all-time (1965–)</span>
        </div>
      </div>
      {gatun.level_spark?.length > 1 && (
        <div className="fr-gat-spark">
          <Sparkline values={gatun.level_spark} width={300} height={26} color="#2d7d9a" />{' '}
          <span>120d</span>
        </div>
      )}
      <div className={`fr-gat-draft ${draftCut > 0 ? 'cut' : ''}`}>
        Projected max draft <b>{gatun.min_projected_neopanamax_draft_ft} ft</b> Neopanamax
        {draftCut > 0 ? (
          <>
            {' '}
            — a <b>{draftCut.toFixed(1)} ft restriction</b> vs the {gatun.normal_max_draft_ft} ft
            norm{gatun.surcharge_pct_now ? `, ${gatun.surcharge_pct_now}% surcharge` : ''}
          </>
        ) : (
          <> — unrestricted (full {gatun.normal_max_draft_ft} ft)</>
        )}
      </div>
      <div className="fr-gat-foot">
        {gatun.source} · as of {gatun.as_of} · {gatun.disclaimer}
      </div>
    </div>
  );
}
