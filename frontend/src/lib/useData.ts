import { useEffect, useState } from 'react';
import type { AppData } from '../types.ts';
import { CORE_FILES, OPTIONAL_SIDECAR_FILES, APPDATA_KEY_MAP } from './layers.gen.ts';

interface DataState {
  loading: boolean;
  error: string | null;
  data: AppData | null;
}

// The fetch manifest is GENERATED from the Python registry (registry/layers.py ->
// layers.gen.ts): CORE_FILES are the measured spine the app blocks on, OPTIONAL_SIDECAR_FILES
// degrade to null when absent, and APPDATA_KEY_MAP maps each data file to the AppData field it
// populates. Adding a layer is one descriptor in the registry — useData picks it up here with
// no hand-edit, so the loader can't drift from the backend (test_registry_codegen gates it).
export function useData(): DataState {
  const [state, setState] = useState<DataState>({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    const base = import.meta.env.BASE_URL || '/';
    const getJson = (f: string): Promise<unknown> =>
      fetch(base + f).then((r) => {
        if (!r.ok) throw new Error(`${f}: ${r.status}`);
        return r.json() as Promise<unknown>;
      });

    // CORE blocks (a missing spine file rejects the whole load); OPTIONAL degrades to null so a
    // missing sidecar hides its feature instead of darkening the globe.
    Promise.all(CORE_FILES.map(getJson))
      .then(async (coreValues) => {
        const optionalValues = await Promise.all(
          OPTIONAL_SIDECAR_FILES.map((f) => getJson(f).catch(() => null)),
        );
        if (!alive) return;
        // Assemble AppData by mapping each file to its registry-declared field. The shape +
        // CORE-required / OPTIONAL-nullable contract is the same one types.ts AppData declares.
        const out: Record<string, unknown> = {};
        CORE_FILES.forEach((f, i) => {
          out[APPDATA_KEY_MAP[f]] = coreValues[i];
        });
        OPTIONAL_SIDECAR_FILES.forEach((f, i) => {
          out[APPDATA_KEY_MAP[f]] = optionalValues[i];
        });
        setState({ loading: false, error: null, data: out as unknown as AppData });
      })
      .catch((e: Error) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
