import { useState } from 'react';

// First-visit explainer — a dismissible corner card so a stranger "gets it" in ~10s.
// Remembered in localStorage; never shown again once dismissed.
const KEY = 'fr_seen_v1';

export default function Onboarding() {
  const [show, setShow] = useState(() => {
    try { return !localStorage.getItem(KEY); } catch { return true; }
  });
  if (!show) return null;
  const dismiss = () => { try { localStorage.setItem(KEY, '1'); } catch { /* ignore */ } setShow(false); };

  return (
    <div className="fr-onb">
      <button className="fr-onb-x" onClick={dismiss} aria-label="dismiss">×</button>
      <div className="fr-onb-title">Welcome to Freight Radar</div>
      <p className="fr-onb-lede">
        A clean monitor of the ~28 ocean-freight chokepoints the world's trade funnels through.
        A statistical engine auto-flags real disruptions — and <b>every number traces to source</b>.
      </p>
      <ul className="fr-onb-list">
        <li><b>Stress index + brief</b> up top — the at-a-glance state of global freight.</li>
        <li><b>Globe + feed</b> — click any flagged chokepoint for the real numbers behind it.</li>
        <li><b>Ask Freight Radar</b> (bottom-right) — a chat that only says what it can cite.</li>
        <li><b>Your data</b> — drop a trade CSV; exposure recomputes in your browser, privately.</li>
      </ul>
      <button className="fr-onb-go" onClick={dismiss}>Explore →</button>
    </div>
  );
}
