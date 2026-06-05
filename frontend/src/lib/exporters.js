// Client-side exports — take the brief or your exposure away with you. No backend.

function download(name, text, type = 'text/plain') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportBrief(brief) {
  if (!brief?.bullets) return;
  const lines = [`FREIGHT RADAR — ${brief.headline}`, `as of ${brief.as_of}`, ''];
  brief.bullets.forEach((b) => lines.push(`• ${b.text.replace(/\*\*/g, '')}`));
  lines.push('', brief.source || 'IMF PortWatch');
  download(`freight-radar-brief-${brief.as_of}.txt`, lines.join('\n'));
}

const csvCell = (c) => {
  const s = c == null ? '' : String(c);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function exportExposureCSV(flags) {
  const rows = [
    [
      'entity',
      'kind',
      'exposed_value_usd',
      'exposed_teu',
      'lane_count',
      'carrying_cost_expected',
      'reroute_premium_expected',
      'cost_of_disruption_expected',
      'working_capital_expected',
      'routing_confidence',
    ],
  ];
  (flags || [])
    .filter((f) => f.lifecycle !== 'resolved' && f.business?.lane_count)
    .forEach((f) => {
      const b = f.business;
      const cs = b.cost_stack || {};
      rows.push([
        f.entity,
        f.kind,
        b.exposed_value_usd,
        b.exposed_teu,
        b.lane_count,
        cs.carrying_cost_of_delay_usd?.expected,
        cs.reroute_premium_usd?.expected,
        cs.total_cost_of_disruption_usd?.expected,
        cs.working_capital_tied_up_usd?.expected,
        b.routing_confidence,
      ]);
    });
  if (rows.length === 1) return;
  download(
    'freight-radar-exposure.csv',
    rows.map((r) => r.map(csvCell).join(',')).join('\n'),
    'text/csv'
  );
}
