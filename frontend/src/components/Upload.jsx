import { useState, useRef } from 'react';
import { lanesFromCSV, TEMPLATE_CSV } from '../lib/csv.js';
import { makeResolver } from '../lib/routing.js';
import { computeExposure } from '../lib/exposure.js';

// In-browser CSV upload — your trade data never leaves the browser. We lazy-load
// the port lookup, resolve your lanes (LOCODE / name / portid), and recompute the
// full cost-of-disruption exposure client-side with the exact same math as the
// pipeline (parity-tested).
let _lookupCache = null;
async function loadLookup() {
  if (_lookupCache) return _lookupCache;
  const base = import.meta.env.BASE_URL || '/';
  const r = await fetch(`${base}data/ports_lookup.json`);
  if (!r.ok) throw new Error('lookup');
  _lookupCache = await r.json();
  return _lookupCache;
}

export default function Upload({ flags, applied, onApply, onReset }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  const handle = async (file) => {
    setBusy(true); setErr(null);
    try {
      const text = await file.text();
      const lanes = lanesFromCSV(text);
      if (!lanes.length) { setErr('No lanes found — check your columns.'); setBusy(false); return; }
      const resolver = makeResolver(await loadLookup());
      const { flags: f, summary } = computeExposure(flags.map((x) => ({ ...x })), lanes, resolver);
      onApply({ summary, flags: f, fileName: file.name, laneCount: lanes.length });
    } catch {
      setErr('Could not read that file.');
    }
    setBusy(false);
  };

  const onDrop = (e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) handle(f); };
  const template = () => {
    const url = URL.createObjectURL(new Blob([TEMPLATE_CSV], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url; a.download = 'freight_radar_template.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  if (applied) {
    return (
      <div className="fr-upl is-on">
        <span className="fr-upl-on">✓ {applied.fileName} · {applied.laneCount} lanes · <b>your data</b></span>
        <span className="fr-upl-priv">nothing left your browser</span>
        <button className="fr-upl-reset" onClick={onReset}>use sample</button>
      </div>
    );
  }

  return (
    <div
      className={`fr-upl ${drag ? 'is-drag' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      <div className="fr-upl-main">
        <span className="fr-upl-title">Use your own trade data</span>
        <span className="fr-upl-sub">{busy ? 'computing…' : 'drop a CSV — it stays in your browser'}</span>
      </div>
      <div className="fr-upl-actions">
        <button className="fr-upl-btn" onClick={() => inputRef.current?.click()} disabled={busy}>Upload CSV</button>
        <button className="fr-upl-link" onClick={template}>template</button>
      </div>
      <input ref={inputRef} type="file" accept=".csv,text/csv" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) handle(f); }} />
      {err && <div className="fr-upl-err">{err}</div>}
    </div>
  );
}
