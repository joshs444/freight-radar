import { useState } from 'react';
import { severityCss } from '../lib/colors.js';
import { money } from '../lib/format.js';
import { Markdown } from '../lib/md.jsx';
import { Sparkline, SparkHistory } from './Sparkline.jsx';
import { computeTrend, trendLabel } from '../lib/trend.js';
import BriefCard from './BriefCard.jsx';
import HazardsPanel from './HazardsPanel.jsx';
import GatunPanel from './GatunPanel.jsx';
import CargoMix from './CargoMix.jsx';
import NationalDependence from './NationalDependence.jsx';
import Upload from './Upload.jsx';
import SearchBox from './SearchBox.jsx';
import { exportBrief, exportExposureCSV } from '../lib/exporters.js';

const CONF_LABEL = { high: 'high', medium: 'derived', low: 'partial', none: 'unrouted' };
const ALERT_C = { RED: '#c0392b', ORANGE: '#c2611f', GREEN: '#3f7a5a' };

function OfficialEvent({ oe }) {
  if (!oe) return null;
  return (
    <div className="fr-oe">
      <span className="fr-oe-badge" style={{ background: ALERT_C[oe.alertlevel] || '#888' }}>{oe.alertlevel}</span>
      <span className="fr-oe-text">
        Official corroboration: <b>{oe.name}</b> ({oe.type_label}, {oe.from} → {oe.to}) — {oe.source}
      </span>
    </div>
  );
}

function StormChip({ storm }) {
  if (!storm) return null;
  const wind = storm.max_wind_kmh ? ` · ${storm.max_wind_kmh} km/h winds` : '';
  return (
    <div className="fr-storm">
      <span className="fr-storm-badge">🌀 {storm.agency}</span>
      <span className="fr-storm-text">
        Possibly related: <b>{storm.category} {storm.name}</b> ~{storm.km} km away{wind} · {storm.basin}
        {storm.url && (
          <> · <a href={storm.url} target="_blank" rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}>forecast</a></>
        )}
        <span className="fr-storm-note">live {storm.source} forecast position — not a confirmed cause</span>
      </span>
    </div>
  );
}

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'critical', label: 'Critical' },
  { key: 'chokepoints', label: 'Chokepoints' },
  { key: 'ports', label: 'Ports' },
];

function Metric({ v, alert }) {
  if (v == null) return <span className="fr-metric fr-dim">—</span>;
  const up = v > 0;
  return (
    <span className={`fr-metric ${alert ? 'fr-hot' : ''}`}>
      {up ? '↑' : '↓'} {up ? '+' : ''}{Math.round(v)}%
    </span>
  );
}

function CostLine({ label, band, strong }) {
  if (!band) return null;
  return (
    <div className={`fr-cost-line ${strong ? 'is-total' : ''}`}>
      <span className="fr-cost-label">{label}</span>
      <span className="fr-cost-val"><b>{money(band.expected)}</b>
        <span className="fr-biz-range"> {money(band.low)}–{money(band.high)}</span>
      </span>
    </div>
  );
}

function BusinessImpact({ b }) {
  const [showWork, setShowWork] = useState(false);
  if (!b) return null;
  if (!b.lane_count) {
    return <div className="fr-biz"><div className="fr-biz-head">Business impact</div>
      <div className="fr-biz-none">No exposure in your trade data.</div></div>;
  }
  const d = b.est_delay_days || {};
  const cs = b.cost_stack || {};
  const carrying = cs.carrying_cost_of_delay_usd || b.carrying_cost_of_delay_usd;
  const reroute = cs.reroute_premium_usd;
  const total = cs.total_cost_of_disruption_usd || b.total_cost_of_disruption_usd;
  const wc = cs.working_capital_tied_up_usd || b.working_capital_tied_up_usd || {};
  const conf = b.routing_confidence;
  return (
    <div className="fr-biz">
      <div className="fr-biz-head">
        Business impact <span className="fr-biz-est">estimate</span>
        {conf && <span className={`fr-biz-conf c-${conf}`}>routing: {CONF_LABEL[conf] || conf}</span>}
      </div>
      <div className="fr-biz-stat">
        <b>{money(b.exposed_value_usd)}</b> of your trade exposed · {b.lane_count} lane{b.lane_count > 1 ? 's' : ''}
        {b.exposed_teu ? ` · ${b.exposed_teu.toLocaleString()} TEU` : ''}
      </div>
      <div className="fr-biz-stat fr-biz-sub">est. <b>+{d.low}–{d.high}d</b> added transit</div>

      <div className="fr-cost-stack">
        <CostLine label="carrying cost of delay" band={carrying} />
        {reroute?.expected > 0 && <CostLine label="reroute premium" band={reroute} />}
        <CostLine label="cost of disruption" band={total} strong />
      </div>
      <div className="fr-biz-stat fr-biz-sub">
        ≈<b>{money(wc.expected)}</b> working capital tied up (locked, not lost — excluded from total)
      </div>

      {b.method?.length > 0 && (
        <>
          <button className="fr-biz-work" onClick={(e) => { e.stopPropagation(); setShowWork((s) => !s); }}>
            {showWork ? '▾' : '▸'} show your work
          </button>
          {showWork && (
            <div className="fr-biz-method">
              {b.method.map((m, i) => (
                <div key={i} className="fr-biz-mline"><code>{m.line}</code> = {m.basis}</div>
              ))}
            </div>
          )}
        </>
      )}
      {b.top_items?.length > 0 && <div className="fr-biz-items">{b.top_items.join(' · ')}</div>}
      <div className="fr-biz-note">
        assumes ~{Math.round((b.carrying_rate_assumed || 0.25) * 100)}%/yr carrying cost · sample trade data — replace with your terms
      </div>
    </div>
  );
}

function MarketBlock({ market, flagId }) {
  const link = market?.items?.[flagId];
  if (!link) return null;
  const inds = market.indicators || {};
  const shown = link.linked.map((k) => inds[k]).filter((v) => v && v.value != null);
  if (!shown.length) return null;
  return (
    <div className="fr-market">
      <div className="fr-market-head">Market context <span>· in this chokepoint's orbit</span></div>
      <div className="fr-market-grid">
        {shown.map((v) => {
          const up = (v.change_pct || 0) >= 0;
          return (
            <div key={v.name} className="fr-mkt">
              <span className="fr-mkt-name">{v.name}{v.estimate ? ' ·est' : ''}</span>
              <span className="fr-mkt-row">
                <b>{v.value}</b><span className="fr-mkt-unit">{v.unit}</span>
                {v.change_pct != null && (
                  <span className={`fr-mkt-chg ${up ? 'up' : 'down'}`}>{up ? '▲' : '▼'} {up ? '+' : ''}{v.change_pct}%</span>
                )}
              </span>
            </div>
          );
        })}
      </div>
      <div className="fr-market-foot">{link.disclaimer}</div>
    </div>
  );
}

function NewsBlock({ news }) {
  if (!news) return null;
  return (
    <div className="fr-news">
      <div className="fr-news-head">Possibly related coverage <span>· not a confirmed cause</span></div>
      {news.items?.length ? (
        news.items.map((a, i) => (
          <span
            key={i}
            className="fr-news-item"
            role="link"
            tabIndex={0}
            onClick={(ev) => { ev.stopPropagation(); window.open(a.url, '_blank', 'noopener'); }}
          >
            <span className="fr-news-title">{a.title}</span>
            <span className="fr-news-meta">{a.source}{a.source && a.published ? ' · ' : ''}{a.published}</span>
          </span>
        ))
      ) : (
        <div className="fr-news-none">No qualifying recent coverage found.</div>
      )}
    </div>
  );
}

function Row({ e, active, onSelect, series, dates, news, market, scrubIndex, watched, onToggleWatch, gatun }) {
  const ser = series?.[e.id];
  const sparkColor = e.critical ? severityCss(e.severity) : '#aab3c0';
  const tl = trendLabel(computeTrend(ser?.values), e.flag?.kind);
  const isWatched = watched?.has(e.id);
  return (
    <button
      className={`fr-row ${active ? 'is-active' : ''} ${e.critical ? 'is-critical' : ''}`}
      onClick={() => onSelect(active ? null : e)}
    >
      <div className="fr-row-main">
        <span
          className={`fr-star ${isWatched ? 'on' : ''}`}
          role="button"
          tabIndex={0}
          title={isWatched ? 'Unwatch' : 'Watch — notify on new/escalated flags'}
          onClick={(ev) => { ev.stopPropagation(); onToggleWatch?.(e.id); }}
        >
          {isWatched ? '★' : '☆'}
        </span>
        {e.critical ? (
          <span className="fr-sev" style={{ color: severityCss(e.severity), borderColor: severityCss(e.severity) }}>
            {e.severity}
          </span>
        ) : (
          <span className="fr-rowdot" />
        )}
        <div className="fr-row-titles">
          <span className="fr-row-name">{e.name}</span>
          <span className="fr-row-sub">
            {e.type}{e.flag ? ` · ${e.flag.kind.replaceAll('_', ' ')}` : ' · normal'}
            {tl && <span className={`fr-trend ${tl.cls}`}> · {tl.arrow} {tl.label}</span>}
          </span>
        </div>
        {ser && <Sparkline values={ser.values} color={sparkColor} mark={scrubIndex} />}
        <Metric v={e.metric} alert={e.critical} />
      </div>
      {active && (
        <div className="fr-row-brief">
          {e.flag && <Markdown text={e.flag.brief_md} />}
          <SparkHistory s={ser} dates={dates} asOf={e.flag?.as_of} baseline={e.flag?.baseline ?? e.baseline} color={sparkColor} />
          {tl && (
            <div className={`fr-trendline ${tl.cls}`}>
              Trending <b>{tl.arrow} {tl.label}</b>
              {tl.pct ? ` — ${tl.pct > 0 ? '+' : ''}${tl.pct}% over the last 10 days` : ''}
            </div>
          )}
          <CargoMix mix={e.cargo_mix} unit={e.type === 'chokepoint' ? 'transits' : 'port calls'}
            avgSize={e.avg_vessel_size_dwt} tonnage={e.capacity_total} />
          {e.type === 'port' && (
            <NationalDependence shareImport={e.share_import} shareExport={e.share_export} country={e.country} />
          )}
          {gatun?.available && gatun.portid === e.id && <GatunPanel gatun={gatun} />}
          {e.flag?.live_storm && <StormChip storm={e.flag.live_storm} />}
          {e.flag?.official_event && <OfficialEvent oe={e.flag.official_event} />}
          {e.flag && <BusinessImpact b={e.flag.business} />}
          {e.flag && market && <MarketBlock market={market} flagId={e.flag.flag_id} />}
          {e.flag && news && <NewsBlock news={news} />}
          <div className="fr-row-meta">
            {e.flag ? <span>{e.flag.method}</span> : <span>{e.type} · monitored</span>}
            {e.flag && <span>as of {e.flag.as_of}</span>}
          </div>
        </div>
      )}
    </button>
  );
}

export default function DataFeed({ rows, filter, setFilter, criticalCount, exposure, upload, search, brief, flags, disruptions, gatun, scrubDate, scrubIndex, onLive, watched, onToggleWatch, onPickEntity, series, dates, news, market, selected, onSelect, asOf, source }) {
  const filters = watched?.size ? [...FILTERS, { key: 'watching', label: `★ ${watched.size}` }] : FILTERS;
  return (
    <aside className="fr-feed">
      <div className="fr-feed-head">
        <span className="fr-feed-title">Monitor</span>
        <span className="fr-feed-count"><b>{criticalCount}</b> critical · {rows.length} shown</span>
      </div>

      {scrubDate && (
        <div className="fr-scrubbing">
          <span>▶ viewing <b>{scrubDate}</b> — feed reflects flags fired by then</span>
          <button onClick={onLive}>back to live</button>
        </div>
      )}

      {search && <SearchBox {...search} />}

      {brief && <BriefCard brief={brief} onPickEntity={onPickEntity} onExport={() => exportBrief(brief)} />}

      {disruptions && <HazardsPanel disruptions={disruptions} onPickEntity={onPickEntity} />}

      {upload && <Upload {...upload} />}

      {exposure && (
        <div className="fr-exposure">
          <div className="fr-exp-label">Your exposure <span>· {upload?.applied ? 'your uploaded data' : 'sample trade data'}</span>
            <button className="fr-exp-export" onClick={() => exportExposureCSV(flags)} title="Download exposure as CSV">↓ csv</button>
          </div>
          <div className="fr-exp-row">
            <div><b>{money(exposure.exposed_value_usd)}</b><span>exposed</span></div>
            <div><b>{money((exposure.total_cost_of_disruption_usd || exposure.carrying_cost_of_delay_usd)?.expected)}</b><span>cost of disruption</span></div>
            <div><b>{exposure.active_disruptions_hitting_you}</b><span>hitting you</span></div>
          </div>
          {exposure.lanes_with_known_route != null && (
            <div className="fr-exp-cov">
              {exposure.lanes_with_known_route} of {exposure.total_flows} lanes modeled ({exposure.coverage_pct}%)
            </div>
          )}
        </div>
      )}

      <div className="fr-filters">
        {filters.map((f) => (
          <button key={f.key} className={`fr-chip ${filter === f.key ? 'on' : ''}`} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>
      <div className="fr-rows">
        {rows.length === 0 && <div className="fr-empty">Nothing to show in this filter.</div>}
        {rows.map((e) => (
          <Row key={e.id} e={e} active={selected?.id === e.id} onSelect={onSelect} series={series} dates={dates}
            news={e.flag ? news?.[e.flag.flag_id] : null} market={market} scrubIndex={scrubIndex}
            watched={watched} onToggleWatch={onToggleWatch} gatun={gatun} />
        ))}
      </div>
      <div className="fr-feed-foot">
        <span>{source}</span>
        <span>as of <b>{asOf}</b></span>
      </div>
    </aside>
  );
}
