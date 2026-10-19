# Design direction

Kozhikode Flood Atlas is a light coastal field atlas: the map is the main visual, with plain-language framing around it. The design should make uncertainty visible without making the page feel alarmist.

## Visual system

- **Canvas:** cool white `#f7faf7`.
- **Secondary surface:** sea mist `#e4f1f5`.
- **Text:** deep coastal ink `#153d3a`.
- **Accent:** teal `#007e91`.
- **Typography:** Public Sans, with a local font file when available and a sensible system fallback.
- **Semantics:** school markers use purple and hospital markers use rose as category colours. Do not turn these into a purple gradient or decorative brand treatment.

Keep the map prominent, use clear hierarchy and generous space, and avoid generic feature-card grids, glass effects, dark-by-default styling, or decorative 3D.

## Motion and interaction

Motion should explain state, not decorate it:

- show a restrained scenario-active indicator;
- give short feedback after a data or scenario update;
- fit the map when a user makes a meaningful selection;
- preserve keyboard focus and readable status text.

Use `prefers-reduced-motion` to remove or shorten transitions while keeping all controls and information available. Do not delay important content for animation.

## Why no 3D

A plan-view atlas benefits from a stable 2D map. Perspective would distort the spatial relationships used for comparison and would not improve the analysis. Lightweight 2D mapping with real relief context is the deliberate choice.

## Implementation boundary

Use vanilla HTML, CSS, and JavaScript with Leaflet. No framework build is needed. Keep data interpretation in explanatory copy and accessible labels rather than relying on colour or motion alone. The publication PNG and caption belong in `artifacts/`; reproducible preparation belongs in `scripts/`; main QA belongs in `tests/`.
