# Run locally

The site is a static vanilla HTML/CSS/JavaScript project. It does not need a framework, package install, build step, or public deployment.

## Preview the map

From the repository root:

```bash
cd site
python3 -m http.server 8000
```

Open <http://localhost:8000/>. Stop the server with `Ctrl+C`.

A local HTTP server is recommended instead of opening `index.html` directly because browsers may restrict local file requests to data and asset files.

## Work on scripts

Scripts belong in `scripts/`. Keep generated publication files and captions in `artifacts/`, and keep main checks in `tests/`. Read the source and limits notes before changing a data label or interpretation. Do not replace the approximately 90 m KSDMA flood grid with terrain shading or treat the DSM as bare-earth elevation.

## Before sharing a change

- Check that scenario labels and the 10/25/50-year counts remain consistent.
- Keep `site/data/observed_status.json` explicit: no verified district-covering observed event layer is included.
- Keep source links and third-party terms in `docs/data-sources.md` and `THIRD_PARTY_NOTICES.md`.
- Run the repository's available checks under `tests/` if they are present.
- Test keyboard focus, narrow screens, map selection feedback, and reduced-motion behaviour.

This preview is an independent screening companion, not an operational warning service. Do not describe a local preview as a public website or live alert system.

## Optional context rebuild

The website runs without the heavy geospatial rebuild dependencies. Rebuilding the
optional terrain relief and waterways context requires the original input tree and
the packages pinned in `scripts/requirements-context.txt`:

```bash
python -m pip install -r scripts/requirements-context.txt
python scripts/prepare_context.py --input-root /path/to/kozhikode_flood
```

`--input-root` is required. It must contain `Kozhikode_boundary.geojson` and the
supplied files under `expansion/improved_context/terrain/` and
`expansion/improved_context/waterways/`. By default the script writes only the
four requested context files under `site/assets/` and `site/data/`; its QA report
is written outside the website at `tests/context_qa.generated.json`. Raw source
grids are not bundled with this repository. This is a context-asset preparation
step only: it does not perform new flood analysis or reproduce the full upstream
pipeline.
