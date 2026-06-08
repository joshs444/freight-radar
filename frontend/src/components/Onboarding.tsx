import { useState } from 'react';

// First-visit explainer — a dismissible corner card so a stranger "gets it" in ~10s.
// It spends its one guaranteed-attention moment routing the visitor to the answer (the
// brief) rather than on a philosophy paragraph. Remembered in localStorage; bumped to v3
// so returning visitors see the new brief-first card once.
const KEY = 'fr_seen_v3';

interface OnboardingProps {
  headline?: string;
  onReadBrief?: () => void;
}

export default function Onboarding({ headline, onReadBrief }: OnboardingProps) {
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
      <div className="fr-onb-kicker">This week in ocean freight</div>
      {headline ? (
        <p className="fr-onb-headline">{headline}</p>
      ) : (
        <div className="fr-onb-title">Welcome to Standpoint</div>
      )}
      <p className="fr-onb-lede">
        The measured freight spine auto-flags real disruptions; news, storms and hazards ride
        alongside as cited, possibly-related context. <b>Every number traces to source.</b>
      </p>
      <div className="fr-onb-actions">
        <button
          className="fr-onb-go"
          onClick={() => {
            onReadBrief?.();
            dismiss();
          }}
        >
          Read the brief ↓
        </button>
        <button className="fr-onb-skip" onClick={dismiss}>
          Explore the globe →
        </button>
      </div>
    </div>
  );
}
