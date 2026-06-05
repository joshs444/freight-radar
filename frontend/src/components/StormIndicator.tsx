import { useState } from 'react';
import type { Storm } from '../types.ts';

interface StormIndicatorProps {
  storms: Storm[] | null | undefined;
  onPick?: (storm: Storm) => void;
}

// Global active-cyclone indicator for the World ribbon (Phase C1) — makes the live
// NHC/GDACS storm layer visible even when no storm is near a flagged port. Shows the
// count; click to list each active system and fly the globe to it. Hidden when none.
export default function StormIndicator({ storms, onPick }: StormIndicatorProps) {
  const [open, setOpen] = useState(false);
  if (!storms?.length) return null;
  return (
    <div className="fr-storms-ind">
      <button
        className={`fr-storms-btn ${open ? 'on' : ''}`}
        onClick={() => setOpen((o) => !o)}
        title="Active tropical cyclones — live NHC + GDACS"
      >
        🌀 <b>{storms.length}</b> active cyclone{storms.length > 1 ? 's' : ''}
      </button>
      {open && (
        <div className="fr-storms-pop">
          <div className="fr-storms-pop-head">
            Active tropical cyclones <span>· live NHC + GDACS</span>
          </div>
          {storms.map((s, i) => (
            <button
              key={s.id || i}
              className="fr-storms-row"
              onClick={() => {
                onPick?.(s);
                setOpen(false);
              }}
            >
              <span className="fr-storms-name">🌀 {s.name}</span>
              <span className="fr-storms-meta">
                {s.category} · {s.basin}
                {s.max_wind_kmh ? ` · ${s.max_wind_kmh} km/h` : ''} · {s.agency}
              </span>
            </button>
          ))}
          <div className="fr-storms-foot">
            click a storm to fly the globe to it · possibly related, not a cause
          </div>
        </div>
      )}
    </div>
  );
}
