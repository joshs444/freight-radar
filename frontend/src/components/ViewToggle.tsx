import type { AppView } from '../types.ts';

// Small segmented control over the stage: switch the same data between the explore-by-
// poking Globe and the scan-and-sort Board. Two views, one data model.
interface ViewToggleProps {
  view: AppView;
  onChange: (v: AppView) => void;
}

const VIEWS: { id: AppView; label: string; glyph: string }[] = [
  { id: 'globe', label: 'Globe', glyph: '◐' },
  { id: 'board', label: 'Board', glyph: '▦' },
  { id: 'data', label: 'SQL', glyph: '⌗' },
  { id: 'ledger', label: 'Sources', glyph: '§' },
];

export default function ViewToggle({ view, onChange }: ViewToggleProps) {
  return (
    <div className="fr-view-toggle" role="group" aria-label="View">
      {VIEWS.map((v) => (
        <button
          key={v.id}
          type="button"
          className={`fr-view-btn ${view === v.id ? 'on' : ''}`}
          aria-pressed={view === v.id}
          onClick={() => onChange(v.id)}
          title={`${v.label} view`}
        >
          <span aria-hidden>{v.glyph}</span> {v.label}
        </button>
      ))}
    </div>
  );
}
