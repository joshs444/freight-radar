import { severityCss } from '../lib/colors.js';
import { money } from '../lib/format.js';
import { Markdown } from '../lib/md.jsx';
import { Sparkline, SparkHistory } from './Sparkline.jsx';
import { computeTrend, trendLabel } from '../lib/trend.js';

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

function BusinessImpact({ b }) {
  if (!b) return null;
  if (!b.lane_count) {
    return <div className="fr-biz"><div className="fr-biz-head">Business impact</div>
      <div className="fr-biz-none">No exposure in your trade data.</div></div>;
  }
  const d = b.est_delay_days || {};
  const cc = b.carrying_cost_of_delay_usd || {};
  const wc = b.working_capital_tied_up_usd || {};
  return (
    <div className="fr-biz">
      <div className="fr-biz-head">Business impact <span className="fr-biz-est">estimate</span></div>
      <div className="fr-biz-stat">
        <b>{money(b.exposed_value_usd)}</b> of your trade exposed · {b.lane_count} lane{b.lane_count > 1 ? 's' : ''}
      </div>
      <div className="fr-biz-stat">
        est. <b>+{d.low}–{d.high}d</b> delay → cost of delay <b>{money(cc.expected)}</b>{' '}
        <span className="fr-biz-range">({money(cc.low)}–{money(cc.high)})</span>
      </div>
      <div className="fr-biz-stat fr-biz-sub">
        ≈<b>{money(wc.expected)}</b> working capital tied up (locked, not lost)
      </div>
      {b.top_items?.length > 0 && <div className="fr-biz-items">{b.top_items.join(' · ')}</div>}
      <div className="fr-biz-note">
        assumes ~{Math.round((b.carrying_rate_assumed || 0.25) * 100)}%/yr carrying cost · replace with your terms
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

function Row({ e, active, onSelect, series, dates, news, market }) {
  const ser = series?.[e.id];
  const sparkColor = e.critical ? severityCss(e.severity) : '#aab3c0';
  const tl = trendLabel(computeTrend(ser?.values), e.flag?.kind);
  return (
    <button
      className={`fr-row ${active ? 'is-active' : ''} ${e.critical ? 'is-critical' : ''}`}
      onClick={() => onSelect(active ? null : e)}
    >
      <div className="fr-row-main">
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
        {ser && <Sparkline values={ser.values} color={sparkColor} />}
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

export default function DataFeed({ rows, filter, setFilter, criticalCount, exposure, series, dates, news, market, selected, onSelect, asOf, source }) {
  return (
    <aside className="fr-feed">
      <div className="fr-feed-head">
        <span className="fr-feed-title">Monitor</span>
        <span className="fr-feed-count"><b>{criticalCount}</b> critical · {rows.length} shown</span>
      </div>

      {exposure && (
        <div className="fr-exposure">
          <div className="fr-exp-label">Your exposure <span>· your trade data</span></div>
          <div className="fr-exp-row">
            <div><b>{money(exposure.exposed_value_usd)}</b><span>exposed</span></div>
            <div><b>{money(exposure.carrying_cost_of_delay_usd?.expected)}</b><span>cost of delay</span></div>
            <div><b>{exposure.active_disruptions_hitting_you}</b><span>hitting you</span></div>
          </div>
        </div>
      )}

      <div className="fr-filters">
        {FILTERS.map((f) => (
          <button key={f.key} className={`fr-chip ${filter === f.key ? 'on' : ''}`} onClick={() => setFilter(f.key)}>
            {f.label}
          </button>
        ))}
      </div>
      <div className="fr-rows">
        {rows.length === 0 && <div className="fr-empty">Nothing to show in this filter.</div>}
        {rows.map((e) => (
          <Row key={e.id} e={e} active={selected?.id === e.id} onSelect={onSelect} series={series} dates={dates}
            news={e.flag ? news?.[e.flag.flag_id] : null} market={market} />
        ))}
      </div>
      <div className="fr-feed-foot">
        <span>{source}</span>
        <span>as of <b>{asOf}</b></span>
      </div>
    </aside>
  );
}
