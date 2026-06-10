# 1. Static committed JSON over a live API

Status: Accepted
Date: 2026-06-05

## Context

Freight Radar is a public portfolio app deployed on GitHub Pages. The data it
visualizes — IMF PortWatch chokepoint/port throughput — is **daily-granularity,
refreshed weekly** by the IMF. There is no value in second-by-second freshness:
the product's value is the auto-flagging + attribution, not refresh speed.

A conventional design would stand a live API in front of the database and have
the browser query it on load. That buys nothing here (the underlying data does
not move between weekly refreshes) and costs a lot: an always-on server to host
and pay for, a runtime dependency that can be down when a reviewer opens the
demo, and a CORS/availability surface area that a static site does not have.

## Decision

The publish step writes a fixed set of **versioned static JSON sidecars**
(`snapshot.json`, `flags.json`, `lanes.json`, plus the optional enricher
sidecars and a `manifest.json`) into `frontend/public/data/`. These are
**committed to the repo** and served as static assets. The React frontend loads
them with plain `fetch(base + 'data/*.json')` (see `frontend/src/lib/useData.ts`)
— there is no backend call on the deployed path.

A read-only FastAPI surface (`backend/freight_radar/api/app.py`) still exists for
the Docker/live deployment, but it serves the **same** published JSON files; it
is an optional path, not a dependency of the live site.

## Consequences

- The deployed site has **no runtime backend** to host, pay for, or keep up. It
  is a pure static bundle; the demo cannot be down because a server is down.
- Every figure on the page is a committed artifact, so the data a reviewer sees
  is exactly the data in the repo — reproducible and inspectable, which serves
  the project's "every number traces to source" brand.
- The cost is freshness latency: the site is only as current as the last
  publish. This is acceptable because PortWatch itself only refreshes weekly,
  and it is mitigated by ADR 5 (a scheduled Action republishes weekly). The UI
  is explicit that the data is never "live" and always stamps its own
  `as of <date>`.
