import { useState, useCallback } from 'react';
import type { Flag } from '../types.ts';

// Watchlist (localStorage) + browser notifications when a watched entity gets a new
// or escalated flag. Establishes a quiet baseline the first time it sees an entity
// (so adding to your watchlist doesn't immediately ping), then only notifies on a
// genuine change vs the last time you loaded the page.
const KEY = 'fr_watch_v1';
const SEEN = 'fr_seen_sev_v1';
const ESCALATE_BY = 10;

// Last-seen severity per portid: a numeric severity, or 'none' when the entity had
// no active flag at the time of the snapshot.
type SeenSeverity = number | 'none';
type SeenMap = Record<string, SeenSeverity>;

const load = <T>(k: string, d: T): T => {
  try {
    return (JSON.parse(localStorage.getItem(k) ?? 'null') as T | null) ?? d;
  } catch {
    return d;
  }
};
const save = (k: string, v: unknown): void => {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* ignore */
  }
};

function ping(title: string, body: string): void {
  try {
    if (Notification.permission === 'granted') new Notification(title, { body });
  } catch {
    /* ignore */
  }
}

export function useWatchlist() {
  const [watched, setWatched] = useState<Set<string>>(() => new Set(load<string[]>(KEY, [])));
  const toggle = useCallback((portid: string) => {
    setWatched((prev) => {
      const n = new Set(prev);
      if (n.has(portid)) n.delete(portid);
      else {
        n.add(portid);
        if ('Notification' in window && Notification.permission === 'default') {
          Notification.requestPermission().catch(() => {});
        }
      }
      save(KEY, [...n]);
      return n;
    });
  }, []);
  return { watched, toggle };
}

// Compare watched entities' current flags to last-seen severity; notify on change.
export function notifyWatched(watched: Set<string>, flags: Flag[]): void {
  if (!watched?.size || !('Notification' in window) || Notification.permission !== 'granted') {
    // still advance the baseline so we don't ping for old news once permission is granted
  }
  const seen = load<SeenMap>(SEEN, {});
  const byPort: Record<string, Flag> = {};
  (flags || [])
    .filter((f) => f.lifecycle !== 'resolved')
    .forEach((f) => {
      byPort[f.portid] = f;
    });
  let changed = false;
  watched.forEach((pid) => {
    const f = byPort[pid];
    const cur: SeenSeverity = f ? f.severity : 'none';
    const prev = seen[pid];
    if (prev !== undefined) {
      if (f && prev === 'none')
        ping(`${f.entity} flagged`, f.headline || 'A new disruption was detected.');
      else if (f && typeof prev === 'number' && f.severity >= prev + ESCALATE_BY) {
        ping(`${f.entity} escalated`, f.headline || `Severity ${prev} → ${f.severity}.`);
      }
    }
    if (prev !== cur) {
      seen[pid] = cur;
      changed = true;
    }
  });
  if (changed) save(SEEN, seen);
}
