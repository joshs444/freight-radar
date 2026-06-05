// Ask Freight Radar — Tier-1, fully client-side, grounded Q&A.
//
// Runs entirely in the browser over the sidecars already loaded (no backend, no
// API key, $0 on GitHub Pages). The hard rule is HONESTY: every number an answer
// states is pulled verbatim from a source JSON and recorded in `facts` with the
// sidecar it came from. The rendered text only ever formats those grounded facts —
// the engine performs no arithmetic that could invent a figure. A node test
// (scripts/check_chat.mjs) verifies, for a battery of questions, that every fact a
// real answer cites actually exists in the cited sidecar. If we can't ground it,
// we don't say it.
//
// Pure functions, no React / browser globals, so the grounding test can import this
// directly under node.

import { money, compact } from './format.js';

// --- formatting (display only — never feeds `facts`) -----------------------
const pct = (v) => (v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v)}%`);
const perDay = (v) => (v == null ? '—' : `${Math.round(v)}/day`);

// a grounded fact: a raw value lifted straight from `src`
const F = (v, src) => ({ v, src });

function answer({ text, facts = [], cites = [], entity = null, kind, suggestions }) {
  return { text, facts, cites: [...new Set(cites)], entity, kind, suggestions };
}

// --- entity aliases (short / common names → canonical) ---------------------
const ALIASES = {
  hormuz: 'strait of hormuz',
  'persian gulf': 'strait of hormuz',
  suez: 'suez canal',
  panama: 'panama canal',
  malacca: 'malacca strait',
  taiwan: 'taiwan strait',
  bosphorus: 'bosporus strait',
  bosporus: 'bosporus strait',
  istanbul: 'bosporus strait',
  gibraltar: 'gibraltar strait',
  kerch: 'kerch strait',
  oresund: 'oresund strait',
  'bab el mandeb': 'bab el-mandeb strait',
  'bab-el-mandeb': 'bab el-mandeb strait',
  mandeb: 'bab el-mandeb strait',
  'red sea': 'bab el-mandeb strait',
  dover: 'dover strait',
  korea: 'korea strait',
  'cape of good hope': 'cape of good hope',
  cape: 'cape of good hope',
  shanghai: 'shanghai (pudong)',
  pudong: 'shanghai (pudong)',
};

function norm(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

// --- build a single lookup over all loaded sidecars ------------------------
export function buildIndex(data) {
  const byId = {};
  const get = (pid, name, type) => (byId[pid] = byId[pid] || { portid: pid, name, type });

  (data?.snapshot?.chokepoints || []).forEach((c) => {
    get(c.portid, c.name, 'chokepoint').snap = c;
  });
  (data?.flags || []).forEach((f) => {
    const r = get(f.portid, f.entity, f.kind?.startsWith('chokepoint') ? 'chokepoint' : 'port');
    if (f.lifecycle !== 'resolved') r.flag = f;
  });
  (data?.stress?.contributors || []).forEach((c) => {
    if (byId[c.portid]) byId[c.portid].contrib = c;
  });
  const series = data?.timeseries?.series || {};
  Object.keys(byId).forEach((pid) => {
    if (series[pid]) byId[pid].series = series[pid];
  });
  // news + market are keyed by flag_id → attach to the entity
  Object.values(byId).forEach((r) => {
    if (!r.flag) return;
    const n = data?.news?.items?.[r.flag.flag_id];
    if (n) r.news = n;
    const m = data?.market?.items?.[r.flag.flag_id];
    if (m) r.market = m;
  });

  // name → portid (chokepoints + flagged ports first; then top ports for "exposed to X")
  const nameToId = {};
  Object.values(byId).forEach((r) => {
    nameToId[norm(r.name)] = r.portid;
  });
  (data?.snapshot?.ports || []).forEach((p) => {
    const n = norm(p.name);
    if (n && !(n in nameToId)) {
      nameToId[n] = p.portid;
      get(p.portid, p.name, 'port').port = p;
    }
  });

  return { byId, nameToId };
}

// find the entity a question refers to (longest match wins; aliases first)
function findEntity(q, index) {
  const qn = ` ${norm(q)} `;
  for (const [alias, canon] of Object.entries(ALIASES)) {
    if (qn.includes(` ${alias} `)) {
      const id = index.nameToId[norm(canon)];
      if (id) return index.byId[id];
    }
  }
  let best = null;
  for (const [name, pid] of Object.entries(index.nameToId)) {
    if (name.length < 4) continue;
    // match the distinctive head of a name ("shanghai" out of "shanghai (pudong)")
    const head = name.split(' (')[0];
    if (qn.includes(` ${name} `) || qn.includes(` ${head} `)) {
      if (!best || name.length > best._len) best = { ...index.byId[pid], _len: name.length };
    }
  }
  return best;
}

// --- answer builders -------------------------------------------------------
function summarize(data) {
  const s = data?.stress;
  const cites = ['stress.json'];
  const facts = [];
  let text = '';
  if (s?.available) {
    facts.push(
      F(s.index, 'stress.json'),
      F(s.wow_delta, 'stress.json'),
      F(s.chokepoints_disrupted, 'stress.json'),
      F(s.chokepoints_total, 'stress.json')
    );
    const mv =
      s.wow_direction === 'up'
        ? `up ${Math.abs(s.wow_delta)}`
        : s.wow_direction === 'down'
          ? `down ${Math.abs(s.wow_delta)}`
          : 'flat';
    text +=
      `Global ocean-freight stress is **${s.index}/100 (${s.label})**, ${mv} week-over-week. ` +
      `**${s.chokepoints_disrupted} of ${s.chokepoints_total}** monitored chokepoints are disrupted.`;
    const top = s.contributors?.[0];
    if (top) {
      facts.push(
        F(top.now, 'stress.json'),
        F(top.normal, 'stress.json'),
        F(top.pct_vs_normal, 'stress.json')
      );
      text +=
        ` The biggest driver is **${top.name}**, running ${perDay(top.now)} vs a normal of ` +
        `${perDay(top.normal)} (${pct(top.pct_vs_normal)}).`;
    }
  } else {
    const n = (data?.flags || []).filter((f) => f.lifecycle !== 'resolved').length;
    text += `${n} active disruptions are being tracked.`;
    cites.push('flags.json');
  }
  return answer({
    text,
    facts,
    cites,
    kind: 'summary',
    suggestions: ['What is the biggest risk?', 'What is improving?', 'What changed this week?'],
  });
}

function entityStatus(e) {
  if (!e) return null;
  const cites = [];
  const facts = [];
  let text = `**${e.name}**`;
  const f = e.flag;
  if (f) {
    cites.push('flags.json');
    facts.push(
      F(f.value, 'flags.json'),
      F(f.baseline, 'flags.json'),
      F(f.pct_change, 'flags.json'),
      F(f.severity, 'flags.json')
    );
    const kind = f.kind.replaceAll('_', ' ');
    text +=
      ` is flagged — **${kind}** (severity ${f.severity}). It ran **${perDay(f.value)}** ` +
      `vs a baseline of ${perDay(f.baseline)} (${pct(f.pct_change)}), detected ${f.as_of}.`;
    if (f.lifecycle) text += ` Lifecycle: ${f.lifecycle}.`;
    // current read from the stress contributor (live, may differ from detection-day)
    if (e.contrib && e.contrib.now != null) {
      facts.push(F(e.contrib.now, 'stress.json'), F(e.contrib.normal, 'stress.json'));
      text += ` It is currently at ${perDay(e.contrib.now)} (normal ~${perDay(e.contrib.normal)}).`;
      cites.push('stress.json');
    }
    if (e.news?.items?.length) {
      facts.push(F(e.news.items.length, 'news.json'));
      text += ` ${e.news.items.length} possibly-related article(s) on file (context, not a confirmed cause).`;
      cites.push('news.json');
    }
    if (f.business?.lane_count) {
      const b = f.business;
      facts.push(F(b.exposed_value_usd, 'flags.json'), F(b.lane_count, 'flags.json'));
      text += ` Against the sample trade book, ${money(b.exposed_value_usd)} across ${b.lane_count} lane(s) route through it.`;
    }
  } else if (e.contrib && e.contrib.now != null) {
    cites.push('stress.json');
    facts.push(
      F(e.contrib.now, 'stress.json'),
      F(e.contrib.normal, 'stress.json'),
      F(e.contrib.pct_vs_normal, 'stress.json')
    );
    text +=
      ` has no active disruption flag, but is currently at ${perDay(e.contrib.now)} ` +
      `vs a normal of ${perDay(e.contrib.normal)} (${pct(e.contrib.pct_vs_normal)}).`;
  } else if (e.snap) {
    cites.push('snapshot.json');
    facts.push(F(e.snap.n_total, 'snapshot.json'));
    text += ` is running ~normal — no active disruption flag (latest ${perDay(e.snap.n_total)}).`;
  } else {
    text += ` is monitored, but has no active disruption flag.`;
    cites.push('snapshot.json');
  }
  return answer({ text, facts, cites, entity: { portid: e.portid, name: e.name }, kind: 'entity' });
}

function biggestRisk(data) {
  const active = (data?.flags || []).filter((f) => f.lifecycle !== 'resolved');
  if (!active.length)
    return answer({
      text: 'No active disruptions right now.',
      cites: ['flags.json'],
      kind: 'risk',
    });
  const top = active.slice().sort((a, b) => b.severity - a.severity)[0];
  const facts = [
    F(top.severity, 'flags.json'),
    F(top.value, 'flags.json'),
    F(top.baseline, 'flags.json'),
    F(top.pct_change, 'flags.json'),
  ];
  const text =
    `The biggest risk is **${top.entity}** — ${top.kind.replaceAll('_', ' ')}, severity ` +
    `**${top.severity}**, running ${perDay(top.value)} vs ${perDay(top.baseline)} (${pct(top.pct_change)}).`;
  return answer({
    text,
    facts,
    cites: ['flags.json'],
    entity: { portid: top.portid, name: top.entity },
    kind: 'risk',
    suggestions: [`Am I exposed to ${top.entity}?`, `Tell me about ${top.entity}`],
  });
}

function trending(data) {
  const s = data?.stress;
  if (!s?.available) return null;
  const facts = [];
  const parts = [];
  if (s.fastest_deteriorating) {
    facts.push(F(s.fastest_deteriorating.delta_stress, 'stress.json'));
    parts.push(`**${s.fastest_deteriorating.name}** is deteriorating fastest`);
  }
  if (s.most_improved) {
    facts.push(F(s.most_improved.delta_stress, 'stress.json'));
    parts.push(`**${s.most_improved.name}** is the most improved`);
  }
  facts.push(F(s.wow_delta, 'stress.json'));
  const mv = s.wow_direction === 'up' ? 'rising' : s.wow_direction === 'down' ? 'falling' : 'flat';
  const sign = s.wow_delta > 0 ? '+' : '';
  const text =
    (parts.length
      ? parts.join(', and ') + ` over the last ${s.fastest_deteriorating?.days || 14} days. `
      : '') + `The overall index is ${mv} (${sign}${s.wow_delta} pts week-over-week).`;
  return answer({ text, facts, cites: ['stress.json'], kind: 'trend' });
}

function exposure(e, data) {
  const ex = data?.exposure;
  // entity-specific exposure
  if (e?.flag?.business?.lane_count) {
    const b = e.flag.business;
    const tot = b.total_cost_of_disruption_usd || b.carrying_cost_of_delay_usd || {};
    const facts = [
      F(b.exposed_value_usd, 'flags.json'),
      F(b.lane_count, 'flags.json'),
      F(tot.expected, 'flags.json'),
    ];
    const text =
      `Through **${e.name}**, ${money(b.exposed_value_usd)} of the sample trade book routes across ` +
      `${b.lane_count} lane(s), an estimated **${money(tot.expected)}** cost of disruption ` +
      `(${money(tot.low)}–${money(tot.high)}; carrying cost + reroute premium). Sample data — swap in your own.`;
    return answer({
      text,
      facts,
      cites: ['flags.json'],
      entity: { portid: e.portid, name: e.name },
      kind: 'exposure',
    });
  }
  if (e && (!e.flag || !e.flag.business?.lane_count)) {
    return answer({
      text: `No lanes in the sample trade book route through **${e.name}**.`,
      cites: ['exposure.json'],
      kind: 'exposure',
    });
  }
  if (!ex)
    return answer({
      text: 'No trade dataset is loaded, so exposure is unavailable.',
      cites: [],
      kind: 'exposure',
    });
  const tot = ex.total_cost_of_disruption_usd || ex.carrying_cost_of_delay_usd || {};
  const facts = [
    F(ex.exposed_value_usd, 'exposure.json'),
    F(ex.active_disruptions_hitting_you, 'exposure.json'),
    F(tot.expected, 'exposure.json'),
    F(ex.lanes_with_known_route, 'exposure.json'),
  ];
  const text =
    `Across the sample trade book (${ex.lanes_with_known_route} of ${ex.total_flows} lanes modeled), ` +
    `**${money(ex.exposed_value_usd)}** routes through disrupted lanes, hit by ${ex.active_disruptions_hitting_you} ` +
    `active disruption(s) — an estimated **${money(tot.expected)}** cost of disruption ` +
    `(${money(tot.low)}–${money(tot.high)}). Sample data — swap in your own.`;
  return answer({ text, facts, cites: ['exposure.json'], kind: 'exposure' });
}

function marketAnswer(data) {
  const inds = data?.market?.indicators;
  if (!inds) return null;
  const want = ['brent', 'wti', 'natgas', 'bunker_vlsfo'];
  const facts = [];
  const lines = [];
  want.forEach((k) => {
    const m = inds[k];
    if (m && m.value != null) {
      facts.push(F(m.value, 'market.json'));
      if (m.change_pct != null) facts.push(F(m.change_pct, 'market.json'));
      lines.push(
        `${m.name} **${m.value}${m.unit ? ' ' + m.unit : ''}** (${pct(m.change_pct)} ${m.change_basis})`
      );
    }
  });
  if (!lines.length) return null;
  const text =
    lines.join('; ') +
    '. Dated market context for the energy-route chokepoints — not a stated cause.';
  return answer({ text, facts, cites: ['market.json'], kind: 'market' });
}

function weekAnswer(data) {
  const b = data?.brief;
  const cites = [];
  const facts = [];
  let text = '';
  const wk = b?.bullets?.find((x) => x.kind === 'week');
  if (wk) {
    // the brief already renders a well-formed, grounded "this week" line
    if (b.new_this_week != null) facts.push(F(b.new_this_week, 'brief.json'));
    text += wk.text;
    cites.push('brief.json');
  } else if (b?.new_this_week != null) {
    facts.push(F(b.new_this_week, 'brief.json'));
    text += `**${b.new_this_week}** disruption(s) were flagged in the last 7 days.`;
    cites.push('brief.json');
  }
  const ev = data?.events;
  if (ev?.events?.length) {
    cites.push('events.json');
    const recent = ev.events
      .slice(0, 3)
      .map((x) => `${x.entity} (${x.type})`)
      .join(', ');
    facts.push(F(ev.event_count, 'events.json'));
    text += ` Recent ledger events: ${recent}.`;
  }
  if (!text) return null;
  return answer({ text: text.trim(), facts, cites, kind: 'week' });
}

function listDisrupted(data) {
  const active = (data?.flags || [])
    .filter((f) => f.lifecycle !== 'resolved')
    .sort((a, b) => b.severity - a.severity);
  if (!active.length)
    return answer({ text: 'Nothing is flagged right now.', cites: ['flags.json'], kind: 'list' });
  const facts = active.map((f) => F(f.severity, 'flags.json'));
  const text =
    `**${active.length}** active disruption(s):\n` +
    active
      .map(
        (f) =>
          `• ${f.entity} — ${f.kind.replaceAll('_', ' ')}, sev ${f.severity} (${pct(f.pct_change)})`
      )
      .join('\n');
  active.forEach((f) => facts.push(F(f.pct_change, 'flags.json')));
  return answer({ text, facts, cites: ['flags.json'], kind: 'list' });
}

function worldAnswer(data) {
  const w = data?.world;
  if (!w?.available || !w.metrics?.length) return null;
  const facts = [];
  const get = (k) => w.metrics.find((m) => m.key === k);
  const parts = [];
  const t = get('transits'),
    pc = get('port_calls'),
    dl = get('delivered'),
    sh = get('shipped');
  if (t) {
    facts.push(F(t.value, 'world.json'), F(t.vs7_pct, 'world.json'));
    parts.push(
      `**${compact(t.value)}** ships in transit through ${w.chokepoints} chokepoints (${t.vs7_pct > 0 ? '+' : ''}${t.vs7_pct}% vs last week)`
    );
  }
  if (pc) {
    facts.push(F(pc.value, 'world.json'));
    parts.push(`**${compact(pc.value)}** port calls across ${w.ports_active} ports`);
  }
  if (dl) {
    facts.push(F(dl.value, 'world.json'));
    parts.push(`**${compact(dl.value)} t** cargo delivered (imports)`);
  }
  if (sh) {
    facts.push(F(sh.value, 'world.json'));
    parts.push(`**${compact(sh.value)} t** shipped (exports)`);
  }
  const text = `Today across global ocean freight: ${parts.join(', ')}. (PortWatch daily estimates, as of ${w.as_of}.)`;
  return answer({ text, facts, cites: ['world.json'], kind: 'world' });
}

function gatunAnswer(data) {
  const g = data?.gatun;
  if (!g?.available) return null;
  const cut = g.normal_max_draft_ft - g.min_projected_neopanamax_draft_ft;
  const facts = [
    F(g.current_level_ft, 'gatun.json'),
    F(g.pctile_alltime, 'gatun.json'),
    F(g.min_projected_neopanamax_draft_ft, 'gatun.json'),
  ];
  if (g.change_30d_ft != null) facts.push(F(g.change_30d_ft, 'gatun.json'));
  const draftLine =
    cut > 0
      ? `projected max draft is **${g.min_projected_neopanamax_draft_ft} ft** Neopanamax — a ${cut.toFixed(1)} ft restriction vs the ${g.normal_max_draft_ft} ft norm${g.surcharge_pct_now ? ` (${g.surcharge_pct_now}% surcharge)` : ''}`
      : `max draft is unrestricted at the full **${g.normal_max_draft_ft} ft**`;
  const text =
    `Panama Canal: Gatun Lake is at **${g.current_level_ft} ft** (${g.pctile_alltime}th percentile of records since 1965` +
    `${g.change_30d_ft != null ? `, ${g.change_30d_ft > 0 ? '+' : ''}${g.change_30d_ft} ft over 30 days` : ''}); ${draftLine}. ` +
    `This is the Panama Canal Authority's own lake/draft data — a leading indicator PortWatch's transit counts can't provide.`;
  return answer({
    text,
    facts,
    cites: ['gatun.json'],
    entity: { portid: g.portid, name: g.name },
    kind: 'gatun',
  });
}

function stressExplain(data) {
  const s = data?.stress;
  if (!s?.available) return null;
  const facts = [
    F(s.index, 'stress.json'),
    F(s.breadth, 'stress.json'),
    F(s.depth, 'stress.json'),
    F(s.chokepoints_disrupted, 'stress.json'),
    F(s.chokepoints_total, 'stress.json'),
  ];
  const top = (s.contributors || [])[0];
  let driver = '';
  if (top) {
    facts.push(
      F(top.now, 'stress.json'),
      F(top.normal, 'stress.json'),
      F(top.pct_vs_normal, 'stress.json')
    );
    driver = ` The biggest driver is **${top.name}** (${perDay(top.now)} vs ${perDay(top.normal)} normal, ${pct(top.pct_vs_normal)}).`;
  }
  const text =
    `The Ocean Freight Stress Index is **our own composite 0–100 score** — not an official index — ` +
    `summarising how disrupted ocean freight is versus normal. It blends **breadth ${s.breadth}** ` +
    `(an economic-weighted average across all ${s.chokepoints_total} chokepoints; ${s.chokepoints_disrupted} disrupted now) ` +
    `with **depth ${s.depth}** (the single worst chokepoint, weighted 40% so one strategic-strait crisis isn't averaged away): ` +
    `index = 0.6×breadth + 0.4×depth = **${s.index}** (${s.label}).${driver} Click the gauge for the full breakdown.`;
  return answer({ text, facts, cites: ['stress.json'], kind: 'stress-explain' });
}

function hazardAnswer(e, data) {
  const d = data?.disruptions;
  const evs = d?.events || [];
  if (!evs.length) {
    return answer({
      text: 'No recent official natural-hazard events affecting monitored ports are on file.',
      cites: ['disruptions.json'],
      kind: 'hazard',
    });
  }
  if (e) {
    const hit = evs.filter(
      (ev) =>
        ev.affected_ports?.some((p) => p.portid === e.portid) ||
        ev.near_chokepoints?.some((c) => c.portid === e.portid)
    );
    if (hit.length) {
      const ev = hit[0];
      return answer({
        text: `**${e.name}** overlaps **${ev.name}** (${ev.type_label}, ${ev.alertlevel} alert, ${ev.from} → ${ev.to}) — IMF PortWatch / GDACS.`,
        facts: [F(ev.n_affected_ports, 'disruptions.json')],
        cites: ['disruptions.json'],
        entity: { portid: e.portid, name: e.name },
        kind: 'hazard',
      });
    }
    return answer({
      text: `No recent official natural-hazard event is on file near **${e.name}**.`,
      cites: ['disruptions.json'],
      entity: { portid: e.portid, name: e.name },
      kind: 'hazard',
    });
  }
  const facts = [F(d.counts?.events, 'disruptions.json'), F(d.counts?.red, 'disruptions.json')];
  const top = evs
    .slice(0, 3)
    .map((ev) => `${ev.name} (${ev.type_label}, ${ev.alertlevel}, ${ev.to})`)
    .join('; ');
  const text =
    `**${d.counts.events}** recent official hazard event(s) hit monitored ports (${d.counts.red} red): ` +
    `${top}. These are dated GDACS alerts (most recent on file), not necessarily active today.`;
  return answer({ text, facts, cites: ['disruptions.json'], kind: 'hazard' });
}

const HELP = answer({
  text:
    "I'm grounded in this dashboard's data — every number I give traces to a source file. " +
    'Try asking about a chokepoint, the biggest risk, what is improving, your exposure, or the market.',
  kind: 'help',
  suggestions: [
    "What's going on?",
    'What is the biggest risk?',
    'Tell me about the Strait of Hormuz',
    'Am I exposed?',
  ],
});

// --- intent routing --------------------------------------------------------
export function ask(q, data, prebuiltIndex) {
  const index = prebuiltIndex || buildIndex(data);
  const s = norm(q);
  if (!s) return HELP;
  const has = (...ws) => ws.some((w) => s.includes(w));
  const e = findEntity(q, index);

  // greetings / help
  if (/^(hi|hey|hello|help|what can you|who are you)\b/.test(s)) return HELP;

  // explain the stress index (what is it / how is it computed / what does it mean)
  if (
    s.includes('stress') &&
    has(
      'what is',
      'what does',
      'how is',
      'how do',
      'how are',
      'explain',
      'mean',
      'calculat',
      'compute',
      'goes into',
      'made up',
      'what makes',
      'made it up',
      'come up with'
    )
  )
    return stressExplain(data) || summarize(data);

  // Panama Canal Gatun lake level / draft (leading indicator)
  if (has('panama', 'gatun', 'draft', 'water level', 'lake level', 'neopanamax', 'canal water'))
    return gatunAnswer(data) || (e ? entityStatus(e) : summarize(data));

  // natural hazards / official events
  if (
    has(
      'weather',
      'storm',
      'cyclone',
      'hurricane',
      'typhoon',
      'earthquake',
      'flood',
      'hazard',
      'natural disaster',
      'official event',
      'gdacs',
      'volcano',
      'tsunami'
    )
  )
    return hazardAnswer(e, data) || HELP;

  // world overview ("how many ships are out / delivered today")
  if (
    has(
      'how many ship',
      'ships out',
      'ships are out',
      'vessels',
      'port call',
      'delivered',
      'shipped',
      'cargo',
      'how busy',
      'world today',
      'global activity',
      'throughput',
      'in transit',
      'how many are out'
    )
  )
    return worldAnswer(data) || summarize(data);

  // market (only if no specific entity intent dominates)
  if (
    has(
      'brent',
      'oil price',
      'crude',
      'bunker',
      'vlsfo',
      'henry hub',
      'natural gas',
      'why is oil',
      'fuel'
    )
  )
    return marketAnswer(data) || HELP;

  // exposure
  if (
    has(
      'exposed',
      'exposure',
      'at risk',
      'my trade',
      'my lanes',
      'hitting me',
      'affect me',
      'impact me'
    )
  )
    return exposure(e, data) || HELP;

  // trend / momentum
  if (
    has(
      'improv',
      'recover',
      'getting worse',
      'worsen',
      'deteriorat',
      'easing',
      'trend',
      'momentum',
      'better or worse'
    )
  )
    return trending(data) || summarize(data);

  // this week / changes
  if (
    has(
      'this week',
      'changed',
      'what is new',
      'whats new',
      'new flag',
      'latest',
      'recently',
      'since last'
    )
  )
    return weekAnswer(data) || summarize(data);

  // biggest risk / worst
  if (
    has(
      'biggest',
      'worst',
      'most critical',
      'most severe',
      'top risk',
      'should i worry',
      'main risk',
      'highest'
    )
  )
    return biggestRisk(data);

  // list
  if (
    has(
      'which',
      'list',
      'all disrupt',
      'what is disrupt',
      'whats disrupt',
      'how many',
      'everything'
    )
  )
    return listDisrupted(data);

  // an entity was named → its status (with vs-normal flavor handled inside)
  if (e) return entityStatus(e);

  // overall state
  if (
    has(
      'going on',
      'happening',
      'summary',
      'overview',
      'state of',
      'how is freight',
      'how bad',
      'stress',
      'situation',
      'overall'
    )
  )
    return summarize(data);

  return HELP;
}

export const SUGGESTED = [
  "What's going on?",
  'How many ships are out today?',
  'What is the biggest risk?',
  'What is improving or worsening?',
  'Tell me about the Strait of Hormuz',
  'Am I exposed?',
];
