# Why the site looks this way

The district map is the main view. The palette comes from coastal geography: sea blue, muted green, pale land and clear labels. It is a flood-exposure tool, not a dramatic warning screen.

The writing uses ordinary words. Source category names are translated into readable labels in the interface, while the downloaded data keeps its original fields.

## Motion with a job

The scenario indicator moves to the selected model. Map changes keep their geographic context. Counts change directly to the real values rather than counting through made-up intermediate numbers. Buttons, disclosure panels and loading states show what is happening.

Reduced-motion preferences disable non-essential animation. You can reach the map without waiting for an introduction. There is no scroll trap or decorative particle field.

## Why the main view stays in 2D

This release uses a 2D map with real surface-relief and waterway context. That is the clearest way to compare the flood footprint with mapped facilities and roads.

A 3D view was considered but is not included. It would not improve the flood model or the exposure calculations. There is no invented flood depth, real-time flow effect or house-level safety estimate.

## A small, readable codebase

The site keeps its existing plain HTML, CSS and JavaScript, with Leaflet handling the map. A framework migration would not improve these tasks, so React and Next.js were not added.

The design review used the available frontend-design, UI/UX, animation, cartography and web-interface guidance. Three.js and 3D architecture guidance were consulted when considering a terrain view. The interface choices serve the flood-map purpose; they are not attributed to the user’s data-link notes.

## What was not added

There are no invented population, land-cover, built-up-area or satellite-change layers. Settlement points are not population exposure. Mapped waterways do not provide the observations or hydraulic data needed to show real water movement. Unverified data stays out of the map.

The public data files are a dated snapshot. There is no automatic refresh, real-time warning feed or house-level safety service. The KSDMA flood grid remains about 90 m; the 30 m surface-relief context does not change it.
