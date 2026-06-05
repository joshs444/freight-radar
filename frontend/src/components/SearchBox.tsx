import { useMemo, useState, useRef, useEffect } from 'react';
import type { Flag, Snapshot } from '../types.ts';

interface SearchEntity {
  portid: string;
  name: string;
  type: 'chokepoint' | 'port';
  flagged: boolean;
  country: string;
}

interface SearchBoxProps {
  snapshot: Snapshot | null;
  flagByPort: Record<string, Flag> | null | undefined;
  onJump: (portid: string) => void;
  onResults?: (ids: string[]) => void;
}

// Search the ~2,065 ports + chokepoints by NAME, COUNTRY, or status, and LIGHT every match
// on the globe (a cyan ring) — not just jump to one. Typed tokens: `country:japan`,
// `is:critical`; bare terms match name + country. Type-ahead dropdown for the top hits.
export default function SearchBox({ snapshot, flagByPort, onJump, onResults }: SearchBoxProps) {
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
      country: '',
    }));
    const pt: SearchEntity[] = (snapshot.ports || []).map((p) => ({
      portid: p.portid,
      name: p.name,
      type: 'port',
      flagged: !!flagByPort?.[p.portid],
      country: p.country || '',
    }));
    return [...ch, ...pt];
  }, [snapshot, flagByPort]);

  // every entity matching the typed query (name/country + tokens). The full set is lit on
  // the globe; the dropdown shows the top few. Tokens: `country:japan`, `is:critical`.
  const allHits = useMemo(() => {
    const raw = q.trim().toLowerCase();
    if (raw.length < 2) return [];
    let wantFlagged = false;
    let countryTok = '';
    const bare: string[] = [];
    for (const t of raw.split(/\s+/)) {
      if (t === 'is:critical' || t === 'is:flagged') wantFlagged = true;
      else if (t.startsWith('country:')) countryTok = t.slice(8);
      else bare.push(t);
    }
    const bareStr = bare.join(' ').trim();
    const hits = entities.filter((e) => {
      if (wantFlagged && !e.flagged) return false;
      if (countryTok && !e.country.toLowerCase().includes(countryTok)) return false;
      if (bareStr && !`${e.name} ${e.country}`.toLowerCase().includes(bareStr)) return false;
      return true;
    });
    hits.sort(
      (a, b) =>
        Number(b.flagged) - Number(a.flagged) ||
        (Number(a.type === 'chokepoint') - Number(b.type === 'chokepoint')) * -1 ||
        a.name.localeCompare(b.name)
    );
    return hits;
  }, [q, entities]);
  const results = useMemo(() => allHits.slice(0, 8), [allHits]);

  // light every match on the globe as you type; clear when the query is emptied
  useEffect(() => {
    onResults?.(allHits.map((e) => e.portid));
  }, [allHits, onResults]);

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
    onResults?.([]);
  };
  const clear = () => {
    setQ('');
    setOpen(false);
    onResults?.([]);
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
      {q && (
        <button className="fr-search-clear" onClick={clear} aria-label="Clear search">
          ×
        </button>
      )}
      {open && allHits.length > 0 && (
        <div className="fr-search-pop">
          <div className="fr-search-count">
            {allHits.length} match{allHits.length === 1 ? '' : 'es'} · lit on the map
          </div>
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
