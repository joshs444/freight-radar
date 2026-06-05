import { useMemo, useState, useRef, useEffect } from 'react';
import type { Flag, Snapshot } from '../types.ts';

interface SearchEntity {
  portid: string;
  name: string;
  type: 'chokepoint' | 'port';
  flagged: boolean;
}

interface SearchBoxProps {
  snapshot: Snapshot | null;
  flagByPort: Record<string, Flag> | null | undefined;
  onJump: (portid: string) => void;
}

// Find one of ~2,065 ports (or a chokepoint) by name and jump to it. Type-ahead
// over the loaded snapshot; flagged/critical entities float to the top.
export default function SearchBox({ snapshot, flagByPort, onJump }: SearchBoxProps) {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  const entities = useMemo<SearchEntity[]>(() => {
    if (!snapshot) return [];
    const ch: SearchEntity[] = (snapshot.chokepoints || []).map((c) => ({
      portid: c.portid,
      name: c.name,
      type: 'chokepoint',
      flagged: !!flagByPort?.[c.portid],
    }));
    const pt: SearchEntity[] = (snapshot.ports || []).map((p) => ({
      portid: p.portid,
      name: p.name,
      type: 'port',
      flagged: !!flagByPort?.[p.portid],
    }));
    return [...ch, ...pt];
  }, [snapshot, flagByPort]);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (s.length < 2) return [];
    const hits = entities.filter((e) => e.name?.toLowerCase().includes(s));
    hits.sort(
      (a, b) =>
        Number(b.flagged) - Number(a.flagged) ||
        (Number(a.type === 'chokepoint') - Number(b.type === 'chokepoint')) * -1 ||
        a.name.toLowerCase().indexOf(s) - b.name.toLowerCase().indexOf(s) ||
        a.name.localeCompare(b.name)
    );
    return hits.slice(0, 8);
  }, [q, entities]);

  useEffect(() => {
    setHi(0);
  }, [q]);
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const choose = (e: SearchEntity | undefined) => {
    if (!e) return;
    onJump(e.portid);
    setQ('');
    setOpen(false);
  };
  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHi((h) => Math.min(h + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHi((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') choose(results[hi]);
    else if (e.key === 'Escape') setOpen(false);
  };

  return (
    <div className="fr-search" ref={boxRef}>
      <span className="fr-search-ico">⌕</span>
      <input
        className="fr-search-in"
        value={q}
        placeholder="Find a port or chokepoint…"
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
      />
      {open && results.length > 0 && (
        <div className="fr-search-pop">
          {results.map((e, i) => (
            <button
              key={e.portid}
              className={`fr-search-row ${i === hi ? 'hi' : ''}`}
              onMouseEnter={() => setHi(i)}
              onClick={() => choose(e)}
            >
              <span className="fr-search-name">{e.name}</span>
              <span className="fr-search-tag">
                {e.flagged && <i className="fr-search-flag" />}
                {e.type}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
