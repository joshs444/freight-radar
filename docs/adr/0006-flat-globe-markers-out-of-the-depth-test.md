# 6. Take flat globe markers out of the deck.gl depth test

Status: Accepted

## Context

The globe renders MapLibre GL v5's native 3D globe with deck.gl v9 layers drawn
in **interleaved** mode, which means deck shares MapLibre's depth buffer. The
chokepoint/port markers are flat, pixel-sized `ScatterplotLayer` discs drawn on
the sphere surface.

They blinked: when zooming in close, each dot would intermittently drop behind
the sphere and pop back. The cause is a depth-encoding disagreement. The v5 globe
writes its surface depth with its own vertex-shader formula, while deck
depth-tests the dots using a perspective near/far from the map transform. At the
same screen pixel the two encodings disagree, so a flat dot's depth straddles the
surface and intermittently fails deck's default `depthCompare: 'less-equal'`. It
worsens with zoom as near-surface depth precision collapses.

## Decision

The flat marker discs are **2-D pixel billboards with no real globe-surface
depth**, so the correct fix is to take them out of the depth test entirely. All
the `ScatterplotLayer` marker layers are given
`{ depthCompare: 'always', depthWriteEnabled: false }` (`frontend/src/Globe.tsx`)
— always pass the depth test, never write depth. (deck.gl v9 / luma.gl v9 removed
the old boolean `depthTest: false`; these are the replacement keys.)

The 3D great-circle `ArcLayer` is **intentionally left depth-tested**, so
back-of-globe trade lanes stay correctly hidden behind the sphere.

## Consequences

- The dots are solid and crisp at every zoom level; the blink is gone. Verified
  with a headless-Chrome check that confirms the globe renders with zero console
  errors.
- Because the flat markers no longer write depth, the globe still reads as a
  solid sphere with no back-side bleed-through, and the arcs — which keep real
  depth — still occlude correctly behind it.
- The fix is specific to the flat 2-D layers; it is not applied blanket to all
  deck layers, preserving correct 3D occlusion where depth actually matters.
