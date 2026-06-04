import { useState } from 'react';

// Natural hazards / official events — IMF PortWatch (GDACS) hazard alerts that hit
// monitored ports/chokepoints. Honestly date-stamped ("most recent"), never implied
// live. Each event lists the real ports it affected; corroborated flags also carry
// an official_event chip in their brief.
const ICON = { TC: '🌀', FL: '🌊', EQ: '◍', VO: '🌋', TS: '🌊', DR: '☀', WF: '🔥' };
const ALERT = { RED: '#c0392b', ORANGE: '#c2611f', GREEN: '#3f7a5a' };

export default function HazardsPanel({ disruptions, onPickEntity }) {
  const [open, setOpen] = useState(false);
  const events = disruptions?.events || [];
  if (!events.length) return null;
  const red = disruptions.counts?.red || 0;

  return (
    <section className="fr-haz">
      <button className="fr-haz-top" onClick={() => setOpen((o) => !o)}>
        <span className="fr-haz-title">Natural hazards · official</span>
        <span className="fr-haz-count">{events.length} recent · {red} red {open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="fr-haz-body">
          {events.slice(0, 8).map((e) => {
            const choke = e.near_chokepoints?.[0];
            return (
              <div key={e.eventid} className="fr-haz-evt">
                <span className="fr-haz-ico" style={{ color: ALERT[e.alertlevel] }}>{ICON[e.type] || '⚠'}</span>
                <div className="fr-haz-main">
                  <div className="fr-haz-name">
                    <span className="fr-haz-alert" style={{ background: ALERT[e.alertlevel] }}>{e.alertlevel}</span>
                    {e.name}
                  </div>
                  <div className="fr-haz-meta">
                    {e.type_label} · {e.from || '?'} → {e.to}
                    {e.n_affected_ports > 0 && ` · ${e.n_affected_ports} port${e.n_affected_ports > 1 ? 's' : ''}`}
                    {choke && (
                      <> · near <button className="fr-haz-link" onClick={(ev) => { ev.stopPropagation(); onPickEntity?.(choke.portid); }}>{choke.name}</button></>
                    )}
                  </div>
                  {e.severity && <div className="fr-haz-sev">{e.severity}</div>}
                  {e.affected_ports?.length > 0 && (
                    <div className="fr-haz-ports">{e.affected_ports.slice(0, 4).map((p) => p.name).join(' · ')}</div>
                  )}
                </div>
              </div>
            );
          })}
          <div className="fr-haz-foot">{disruptions.source} · trailing {disruptions.window_days}d</div>
        </div>
      )}
    </section>
  );
}
