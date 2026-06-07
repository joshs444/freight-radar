import { useEffect, useMemo, useRef, useState } from 'react';
import type { AppView } from '../types.ts';
import type { LayerId, LayerVisibility } from '../lib/layers.gen.ts';
import { LAYER_SECTIONS } from '../lib/layers.gen.ts';
import { LENSES } from '../lib/lenses.ts';
import type { Lens } from '../lib/lenses.ts';

interface CommandPaletteProps {
  layers: LayerVisibility;
  onToggleLayer: (id: LayerId) => void;
  view: AppView;
  onChangeView: (v: AppView) => void;
  availableLayers: Set<LayerId>; // layers that actually have data right now
  onApplyLens: (lens: Lens) => void;
}

interface Command {
  key: string;
  group: string;
  label: string;
  hint: string;
  run: () => void;
  on?: boolean;
}

const VIEW_LABELS: { id: AppView; label: string }[] = [
  { id: 'globe', label: 'Globe' },
  { id: 'board', label: 'Board' },
  { id: 'data', label: 'Data feed' },
  { id: 'ledger', label: 'Source ledger' },
];

// ⌘K / Ctrl-K command palette — the one box to navigate the whole instrument: jump to any
// view, toggle any (available) layer, or load a curated lens. Self-contained: it installs
// its own global hotkey + open state and takes only data + action callbacks. Discovery
// (this) + recall (lenses) is how 30+ layers stay navigable without a wall of switches.
export default function CommandPalette({
  layers,
  onToggleLayer,
  view,
  onChangeView,
  availableLayers,
  onApplyLens,
}: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [hi, setHi] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // global ⌘K / Ctrl-K toggles the palette from anywhere (even while a field is focused);
  // a 'fr:open-palette' window event opens it too (the header chip, for mouse/touch users)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener('keydown', onKey);
    window.addEventListener('fr:open-palette', onOpen);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('fr:open-palette', onOpen);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQ('');
      setHi(0);
      // focus after the modal paints
      const t = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(t);
    }
  }, [open]);

  // click-outside the dialog closes it (document listener, not a handler on the backdrop —
  // keeps the overlay a non-interactive presentation element for a11y)
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const commands = useMemo<Command[]>(() => {
    const cmds: Command[] = [];
    // views
    for (const v of VIEW_LABELS) {
      if (v.id === view) continue;
      cmds.push({
        key: `view:${v.id}`,
        group: 'Go to',
        label: v.label,
        hint: 'view',
        run: () => onChangeView(v.id),
      });
    }
    // lenses
    for (const lens of LENSES) {
      cmds.push({
        key: `lens:${lens.id}`,
        group: 'Load lens',
        label: lens.name,
        hint: lens.blurb,
        run: () => onApplyLens(lens),
      });
    }
    // layer toggles (only those with data available)
    for (const section of LAYER_SECTIONS) {
      for (const row of section.rows) {
        if (!availableLayers.has(row.id)) continue;
        const on = layers[row.id];
        cmds.push({
          key: `layer:${row.id}`,
          group: `Toggle · ${section.title}`,
          label: row.label,
          hint: on ? 'on' : 'off',
          on,
          run: () => onToggleLayer(row.id),
        });
      }
    }
    return cmds;
  }, [view, layers, availableLayers, onChangeView, onApplyLens, onToggleLayer]);

  const filtered = useMemo(() => {
    const raw = q.trim().toLowerCase();
    if (!raw) return commands;
    return commands.filter((c) => `${c.label} ${c.group} ${c.hint}`.toLowerCase().includes(raw));
  }, [q, commands]);

  useEffect(() => {
    setHi(0);
  }, [q]);

  if (!open) return null;

  const run = (c: Command | undefined) => {
    if (!c) return;
    c.run();
    // toggles keep the palette open (toggle several at once); navigations close it
    if (!c.key.startsWith('layer:')) setOpen(false);
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHi((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      run(filtered[hi]);
    }
  };

  // group consecutive commands under their group heading for the rendered list
  let lastGroup = '';

  return (
    <div className="fr-cmdk-backdrop" role="presentation">
      <div className="fr-cmdk" ref={dialogRef} role="dialog" aria-label="Command palette">
        <input
          ref={inputRef}
          className="fr-cmdk-input"
          value={q}
          placeholder="Jump to a view, toggle a layer, or load a lens…"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
        />
        <div className="fr-cmdk-list">
          {filtered.length === 0 && <div className="fr-cmdk-empty">No matches</div>}
          {filtered.map((c, i) => {
            const head = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <div key={c.key}>
                {head && <div className="fr-cmdk-group">{head}</div>}
                <button
                  className={`fr-cmdk-row ${i === hi ? 'hi' : ''}`}
                  onMouseEnter={() => setHi(i)}
                  onClick={() => run(c)}
                >
                  <span className="fr-cmdk-label">{c.label}</span>
                  <span
                    className={`fr-cmdk-hint ${c.on === true ? 'on' : c.on === false ? 'off' : ''}`}
                  >
                    {c.hint}
                  </span>
                </button>
              </div>
            );
          })}
        </div>
        <div className="fr-cmdk-foot">
          <span>
            <kbd>↑</kbd>
            <kbd>↓</kbd> navigate
          </span>
          <span>
            <kbd>↵</kbd> run
          </span>
          <span>
            <kbd>esc</kbd> close
          </span>
        </div>
      </div>
    </div>
  );
}
