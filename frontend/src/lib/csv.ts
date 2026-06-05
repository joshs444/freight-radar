// Minimal dependency-free CSV → objects (handles quoted fields, escaped quotes,
// CRLF). Plus a tolerant mapper from arbitrary trade-CSV headers to lane objects,
// so a user doesn't have to match our exact column names.

export function parseCSV(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let field = '',
    row: string[] = [],
    inQ = false,
    i = 0;
  const pushF = () => {
    row.push(field);
    field = '';
  };
  const pushR = () => {
    rows.push(row);
    row = [];
  };
  while (i < text.length) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else inQ = false;
      } else field += c;
    } else if (c === '"') inQ = true;
    else if (c === ',') pushF();
    else if (c === '\n') {
      pushF();
      pushR();
    } else if (c !== '\r') field += c;
    i++;
  }
  if (field.length || row.length) {
    pushF();
    pushR();
  }
  const header = (rows.shift() || []).map((h) => h.trim().toLowerCase());
  return rows
    .filter((r) => r.some((c) => c !== ''))
    .map(
      (r): Record<string, string> =>
        Object.fromEntries(header.map((h, j) => [h, (r[j] ?? '').trim()]))
    );
}

const ALIASES: Record<string, string[]> = {
  lane_id: ['lane_id', 'id', 'lane', 'route_id'],
  origin_port: ['origin_port', 'origin', 'from', 'from_port', 'load_port', 'pol', 'origin port'],
  dest_port: [
    'dest_port',
    'destination',
    'destination_port',
    'to',
    'to_port',
    'discharge_port',
    'pod',
    'dest port',
  ],
  origin_region: ['origin_region', 'from_region', 'origin region'],
  dest_region: ['dest_region', 'to_region', 'destination_region', 'dest region'],
  item_category: ['item_category', 'item', 'category', 'commodity', 'product', 'goods'],
  annual_value_usd: [
    'annual_value_usd',
    'value',
    'annual_value',
    'value_usd',
    'usd',
    'annual value',
  ],
  annual_teu: ['annual_teu', 'teu', 'annual_teus', 'volume_teu'],
};

const pick = (obj: Record<string, string>, names: string[]): string => {
  for (const n of names) if (obj[n] != null && obj[n] !== '') return obj[n];
  return '';
};
const num = (s: string): number => {
  const v = parseFloat(String(s).replace(/[, $]/g, ''));
  return Number.isFinite(v) ? v : 0;
};

export interface CsvLane {
  lane_id: string;
  origin_region: string;
  dest_region: string;
  origin_port: string;
  dest_port: string;
  item_category: string;
  annual_value_usd: number;
  annual_teu: number;
}

export function lanesFromCSV(text: string): CsvLane[] {
  const objs = parseCSV(text);
  return objs
    .map((o, i) => ({
      lane_id: pick(o, ALIASES.lane_id) || `L${i + 1}`,
      origin_region: pick(o, ALIASES.origin_region),
      dest_region: pick(o, ALIASES.dest_region),
      origin_port: pick(o, ALIASES.origin_port),
      dest_port: pick(o, ALIASES.dest_port),
      item_category: pick(o, ALIASES.item_category) || 'Goods',
      annual_value_usd: num(pick(o, ALIASES.annual_value_usd)),
      annual_teu: num(pick(o, ALIASES.annual_teu)),
    }))
    .filter((l) => l.origin_port || l.dest_port);
}

export const TEMPLATE_CSV =
  'lane_id,origin_region,origin_port,dest_region,dest_port,item_category,annual_value_usd,annual_teu\n' +
  'L01,East Asia,Shanghai (Pudong),North Europe,Rotterdam,Electronics,58000000,4200\n' +
  'L02,Gulf,Jebel Ali,North Europe,Rotterdam,Petrochemicals,41000000,1200\n' +
  'L03,,CNSGH,,USLAX,Apparel,21000000,2600\n';
