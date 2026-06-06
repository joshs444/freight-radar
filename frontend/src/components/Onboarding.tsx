import { useState } from 'react';

// First-visit explainer — a dismissible corner card so a stranger "gets it" in ~10s.
// Remembered in localStorage; never shown again once dismissed.
const KEY = 'fr_seen_v2';

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
      <div className="fr-onb-title">Welcome to Standpoint</div>
      <p className="fr-onb-lede">
        World signals on one honest globe. Ocean-freight throughput is the measured spine — a
        statistical engine auto-flags real disruptions — while news, storms and hazards ride
        alongside as cited, possibly-related context.{' '}
        <b>Every number traces to source; nothing here forecasts.</b>
      </p>
      <button className="fr-onb-go" onClick={dismiss}>
        Explore →
      </button>
    </div>
  );
}
