import { useState } from 'react';

// First-visit explainer — a dismissible corner card so a stranger "gets it" in ~10s.
// Remembered in localStorage; never shown again once dismissed.
const KEY = 'fr_seen_v1';

export default function Onboarding() {
  const [show, setShow] = useState(() => {
    try {
      return !localStorage.getItem(KEY);
    } catch {
      return true;
    }
  });
  if (!show) return null;
  const dismiss = () => {
    try {
      localStorage.setItem(KEY, '1');
    } catch {
      /* ignore */
    }
    setShow(false);
  };

  return (
    <div className="fr-onb">
      <button className="fr-onb-x" onClick={dismiss} aria-label="Dismiss the welcome message">
        ×
      </button>
      <div className="fr-onb-title">Welcome to Freight Radar</div>
      <p className="fr-onb-lede">
        A clean monitor of the ~28 ocean-freight chokepoints the world's trade funnels through — a
        statistical engine auto-flags real disruptions, and <b>every number traces to source</b>.
      </p>
      <button className="fr-onb-go" onClick={dismiss}>
        Explore →
      </button>
    </div>
  );
}
