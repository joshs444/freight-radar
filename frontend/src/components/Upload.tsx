import { useState, useRef } from 'react';
import { lanesFromCSV, TEMPLATE_CSV } from '../lib/csv.ts';
import { makeResolver } from '../lib/routing.ts';
import { computeExposure } from '../lib/exposure.ts';
import type { PortLookup } from '../lib/routing.ts';
import type { Flag, ExposureSummary } from '../types.ts';

export interface AppliedExposure {
  summary: ExposureSummary;
  flags: Flag[];
  fileName: string;
  laneCount: number;
}

interface UploadProps {
  flags: Flag[];
  applied: AppliedExposure | null;
  onApply: (result: AppliedExposure) => void;
  onReset: () => void;
}

// In-browser CSV upload — your trade data never leaves the browser. We lazy-load
// the port lookup, resolve your lanes (LOCODE / name / portid), and recompute the
// full cost-of-disruption exposure client-side with the exact same math as the
// pipeline (parity-tested).
let _lookupCache: PortLookup | null = null;
async function loadLookup(): Promise<PortLookup> {
  if (_lookupCache) return _lookupCache;
  const base = import.meta.env.BASE_URL || '/';
  const r = await fetch(`${base}data/ports_lookup.json`);
  if (!r.ok) throw new Error('lookup');
  const lookup = (await r.json()) as PortLookup;
  _lookupCache = lookup;
  return lookup;
}

export default function Upload({ flags, applied, onApply, onReset }: UploadProps) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handle = async (file: File) => {
    setBusy(true);
    setErr(null);
    try {
      const text = await file.text();
      const lanes = lanesFromCSV(text);
      if (!lanes.length) {
        setErr('No lanes found — check your columns.');
        setBusy(false);
        return;
      }
      const resolver = makeResolver(await loadLookup());
      const { flags: f, summary } = computeExposure(
        flags.map((x) => ({ ...x })),
        lanes,
        resolver
      );
      onApply({ summary, flags: f, fileName: file.name, laneCount: lanes.length });
    } catch {
      setErr('Could not read that file.');
    }
    setBusy(false);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handle(f);
  };
  const template = () => {
    const url = URL.createObjectURL(new Blob([TEMPLATE_CSV], { type: 'text/csv' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'freight_radar_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (applied) {
    return (
      <div className="fr-upl is-on">
        <span className="fr-upl-on">
          ✓ {applied.fileName} · {applied.laneCount} lanes · <b>your data</b>
        </span>
        <span className="fr-upl-priv">nothing left your browser</span>
        <button className="fr-upl-reset" onClick={onReset}>
          use sample
        </button>
      </div>
    );
  }

  return (
    // Drag-and-drop is a pointer-only enhancement; the keyboard-accessible path is the
    // native "Upload CSV" button below (which opens the file picker).
    <div
      className={`fr-upl ${drag ? 'is-drag' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      <div className="fr-upl-main">
        <span className="fr-upl-title">Use your own trade data</span>
        <span className="fr-upl-sub">
          {busy ? 'computing…' : 'drop a CSV — it stays in your browser'}
        </span>
      </div>
      <div className="fr-upl-actions">
        <button className="fr-upl-btn" onClick={() => inputRef.current?.click()} disabled={busy}>
          Upload CSV
        </button>
        <button className="fr-upl-link" onClick={template}>
          template
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handle(f);
        }}
      />
      {err && <div className="fr-upl-err">{err}</div>}
    </div>
  );
}
