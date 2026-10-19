'use strict';

const DATA_ROOT = 'data/';
const SCENARIOS = [10, 25, 50];
const PAGE_SIZE = 10;
const LAYER_IDS = [
  'model',
  'schools',
  'hospitals',
  'roads',
  'settlements',
  'local',
  'terrain',
  'waterways',
  'observed',
  'coverage',
  'locations',
  'street',
];
const numberFormat = new Intl.NumberFormat('en-IN');
const decimalFormat = new Intl.NumberFormat('en-IN', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const state = {
  year: 50,
  scope: '',
  healthType: '',
  sort: 'name',
  sortDirection: 'ascending',
  page: 1,
  map: null,
  bounds: null,
  layers: {},
  data: {},
  flood: {},
  roadOverlaps: {},
  reducedMotion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
  dataPromise: null,
  eventsBound: false,
  initialLayerDefaults: {},
  mapLocked: false,
  locationStatus: 'Loading local-body centre coverage…',
};

const get = (id) => document.getElementById(id);
const has = (id) => Boolean(get(id));
const formatNumber = (value) => numberFormat.format(Number(value || 0));
const formatDecimal = (value) => decimalFormat.format(Number(value || 0));
const escapeHtml = (value) =>
  String(value ?? '').replace(
    /[&<>"']/g,
    (character) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character],
  );
const checked = (id) => has(id) && get(id).checked;
const reducedMotion = () =>
  state.reducedMotion || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function fetchJson(file) {
  return fetch(`${DATA_ROOT}${file}`).then((response) => {
    if (!response.ok) throw new Error(`Unable to load ${file} (${response.status})`);
    return response.json();
  });
}

function setLoadingProgress(value, message) {
  const progress = get('load-progress');
  if (progress) progress.value = Math.max(0, Math.min(100, value));
  if (has('load-message')) get('load-message').textContent = message;
  if (has('map-status')) get('map-status').textContent = message;
}

async function loadWithProgress(file, completed, total) {
  const result = await fetchJson(file);
  setLoadingProgress(
    (completed() / total) * 100,
    `Loaded ${completed()} of ${total} model and asset files…`,
  );
  return result;
}

function safeSourceLink(url, label) {
  const anchor = document.createElement('a');
  try {
    const parsed = new URL(url, window.location.href);
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('Unsupported URL scheme');
    anchor.href = parsed.href;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.textContent = label || parsed.hostname;
    return anchor;
  } catch {
    return document.createTextNode(label || 'Source link unavailable');
  }
}

function appendParagraph(parent, text) {
  if (!parent || !text) return;
  const paragraph = document.createElement('p');
  paragraph.textContent = text;
  parent.append(paragraph);
}

function setLayerVisible(layer, visible) {
  if (!layer || !state.map) return;
  if (visible && !state.map.hasLayer(layer)) layer.addTo(state.map);
  if (!visible && state.map.hasLayer(layer)) state.map.removeLayer(layer);
}

function updateLoadingControls(disabled) {
  document.querySelectorAll('button, input, select').forEach((control) => {
    if (control.id !== 'retry-load') control.disabled = disabled;
  });
  if (!disabled && state.data.localRows) renderLocalTable();
}

function setOptionalContextStatus(kind, message, failed = false) {
  const control = get(`layer-${kind}`);
  if (control) {
    control.disabled = failed;
    if (failed) control.checked = false;
    const label = control.closest('label');
    if (label) label.title = message;
  }
  showToast(message);
}

function readUrlState() {
  const params = new URLSearchParams(window.location.search);
  const requestedYear = Number(params.get('scenario'));
  state.year = SCENARIOS.includes(requestedYear) ? requestedYear : 50;
  state.scope = params.get('area') || '';
  state.page = Math.max(1, Math.floor(Number(params.get('page')) || 1));
  const requestedHealthType = params.get('health') || '';
  const healthTypes = [
    'hospital',
    'clinic',
    'centre',
    'health_post',
    'doctor',
    'community_health_worker',
    'rehabilitation',
  ];
  state.healthType = healthTypes.includes(requestedHealthType) ? requestedHealthType : '';
  if (has('health-type')) get('health-type').value = state.healthType;
  if (has('local-search')) get('local-search').value = params.get('q') || '';
  const requestedLayers = params.get('layers');
  LAYER_IDS.forEach((token) => {
    const control = get(`layer-${token}`);
    if (!control) return;
    if (requestedLayers !== null) control.checked = requestedLayers.split(',').includes(token);
    else if (Object.prototype.hasOwnProperty.call(state.initialLayerDefaults, token))
      control.checked = state.initialLayerDefaults[token];
  });
  if (has('only-overlap')) get('only-overlap').checked = params.get('overlaps') !== '0';
  const sort = params.get('sort');
  const direction = params.get('direction');
  if (['name', 'type', 'schools', 'hospitals', 'roads'].includes(sort)) state.sort = sort;
  if (direction === 'ascending' || direction === 'descending') state.sortDirection = direction;
}

function writeUrlState(replace = true) {
  const params = new URLSearchParams();
  params.set('scenario', String(state.year));
  if (state.scope) params.set('area', state.scope);
  if (state.healthType) params.set('health', state.healthType);
  const activeLayers = LAYER_IDS.filter((token) => checked(`layer-${token}`));
  if (activeLayers.length) params.set('layers', activeLayers.join(','));
  if (has('only-overlap') && !checked('only-overlap')) params.set('overlaps', '0');
  const query = has('local-search') ? get('local-search').value.trim() : '';
  if (query) params.set('q', query);
  if (state.page > 1) params.set('page', String(state.page));
  if (state.sort !== 'name') params.set('sort', state.sort);
  if (state.sortDirection !== 'ascending') params.set('direction', state.sortDirection);
  const url = `${window.location.pathname}?${params.toString()}${window.location.hash}`;
  window.history[replace ? 'replaceState' : 'pushState']({}, '', url);
}

function selectedLocalBody() {
  return state.data.localRows?.find((row) => String(row.id) === state.scope) || null;
}

function selectedStats() {
  if (!state.scope)
    return state.data.summary?.find((row) => row.return_period_years === state.year) || null;
  const body = selectedLocalBody();
  if (!body) return null;
  return {
    schools_overlap: body[`schools_overlap_${state.year}`],
    schools_total_mapped: body.schools_total,
    hospitals_overlap: body[`hospitals_overlap_${state.year}`],
    hospitals_total_mapped: body.hospitals_total,
    major_roads_overlap_km: body[`roads_overlap_km_${state.year}`],
    major_roads_total_km: body.roads_total_km,
  };
}

function updateStats() {
  const stats = selectedStats();
  if (!stats) return;
  get('school-count').textContent = formatNumber(stats.schools_overlap);
  get('hospital-count').textContent = formatNumber(stats.hospitals_overlap);
  get('road-count').textContent = `${formatDecimal(stats.major_roads_overlap_km)} km`;
  get('school-total').textContent = `of ${formatNumber(stats.schools_total_mapped)} mapped records`;
  get('hospital-total').textContent =
    `of ${formatNumber(stats.hospitals_total_mapped)} mapped records`;
  get('road-total').textContent = `of ${formatDecimal(stats.major_roads_total_km)} mapped km`;
  get('scope-name').textContent = state.scope
    ? selectedLocalBody()?.name || 'Selected body'
    : 'Whole district';
  document.querySelectorAll('button[data-year]').forEach((button) => {
    const active = Number(button.dataset.year) === state.year;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  if (has('table-scenario'))
    get('table-scenario').textContent =
      `${state.year}-year scenario · ${100 / state.year}% annual exceedance`;
  if (has('scenario-chance'))
    get('scenario-chance').textContent =
      `${100 / state.year}% chance of being exceeded in any year—not once every ${state.year} years.`;
  document.documentElement.style.setProperty(
    '--scenario-index',
    String(Math.max(0, SCENARIOS.indexOf(state.year))),
  );
  if (has('map-status'))
    get('map-status').textContent =
      `${state.year}-year model · ${100 / state.year}% annual exceedance${state.scope ? ' · local body highlighted' : ''}`;
  document
    .querySelectorAll('#scenario-rows tr')
    .forEach((row) =>
      row.classList.toggle('scenario-row-active', Number(row.dataset.year) === state.year),
    );
  window.exposureState = {
    year: state.year,
    scope: state.scope,
    stats,
    observedAvailable: Boolean(state.data.observed?.available),
  };
  const statsElement = get('stats');
  if (statsElement) {
    statsElement.classList.remove('stats-updated');
    if (!reducedMotion()) requestAnimationFrame(() => statsElement.classList.add('stats-updated'));
  }
}

function healthClassLabel(properties) {
  if (properties.kind === 'school') return 'School record';
  const labels = {
    hospital: 'Hospital',
    clinic: 'Clinic',
    centre: 'Health centre',
    doctor: 'Doctor or medical practice',
    doctors: 'Doctor or medical practice',
    health_post: 'Health post',
    community_health_worker: 'Community health worker',
    rehabilitation: 'Rehabilitation service',
  };
  return `${labels[properties.healthcare_class] || 'Health record'} (OSM classification)`;
}

function sourceEditMarkup(properties) {
  if (!properties.source_edit_timestamp)
    return '<p>The source did not supply an OSM edit date. This record has not been field-verified.</p>';
  const value = new Date(properties.source_edit_timestamp);
  const label = Number.isNaN(value.getTime())
    ? 'Unavailable'
    : value.toLocaleDateString('en-IN', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        timeZone: 'UTC',
      });
  return `<p>Last OSM record edit: ${escapeHtml(label)}. This is not an inspection date.</p>`;
}

function facilityPopup(properties) {
  const overlap = properties[`overlap_${state.year}yr`];
  const osmId = String(properties.osm_id || '');
  const source = /^(node|way|relation)\/\d+$/.test(osmId)
    ? `<p><a href="https://www.openstreetmap.org/${escapeHtml(osmId)}" target="_blank" rel="noopener noreferrer">OSM source record</a></p>`
    : '';
  const labels = {
    official_directory_match:
      'Name and locality matched an official source. This does not prove operating status or location accuracy.',
    official_identity_unresolved:
      'The official-source review did not establish a reliable identity match.',
    not_independently_checked: 'Not independently checked.',
  };
  let evidence = '';
  if (properties.verification_evidence_url) {
    const paragraph = document.createElement('p');
    paragraph.append(safeSourceLink(properties.verification_evidence_url, 'Identity-check source'));
    evidence = paragraph.outerHTML;
  }
  return `<h3>${escapeHtml(properties.name || 'Unnamed mapped record')}</h3>
    <p>${escapeHtml(healthClassLabel(properties))} · ${escapeHtml(osmId)}</p>
    <p><strong>${overlap ? 'Mapped geometry overlaps' : 'No overlap shown with'} the ${state.year}-year footprint.</strong></p>
    <p>Geometric screening only—not confirmed inundation, damage or operating status. The symbol is a locator.</p>
    <p><strong>Identity review:</strong> ${escapeHtml(labels[properties.verification_status] || 'Not independently checked.')}</p>
    ${properties.classification_warning ? `<p>${escapeHtml(properties.classification_warning)}</p>` : ''}
    ${properties.lifecycle_ambiguous ? '<p>Lifecycle tags need review. Current use is not confirmed.</p>' : ''}
    ${sourceEditMarkup(properties)}${evidence}${source}`;
}

function locationPopup(feature) {
  const properties = feature.properties || {};
  const local = state.data.localRows?.find((row) => String(row.id) === String(properties.id));
  const type = localTypeLabel(properties.type);
  return `<h3>${escapeHtml(properties.name || local?.name || 'Unnamed local body')}</h3><p>${escapeHtml(type)} · Approximate area centre</p><p>Point locator only—not an office, boundary or exact address. No directions or Google Maps-derived data are used.</p>${local ? `<button type="button" class="popup-select-local" data-local-id="${escapeHtml(properties.id)}">Select this local body</button>` : '<p>Local-body record was not found in the comparison table.</p>'}`;
}

function renderLocations() {
  if (state.layers.locations) state.map.removeLayer(state.layers.locations);
  state.layers.locations = L.layerGroup();
  const features = state.data.locations?.features || [];
  features.forEach((feature) => {
    const properties = feature.properties || {};
    const coordinates = feature.geometry?.coordinates || [];
    if (coordinates.length < 2) return;
    const icon = L.divIcon({
      className: 'map-label',
      html: `<span class="location-marker location-${escapeHtml(properties.type || 'local')}"><span class="visually-hidden">Approximate area centre: </span></span>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    });
    L.marker([coordinates[1], coordinates[0]], {
      icon,
      title: `${properties.name || 'Local body'} — approximate area centre`,
      keyboard: true,
    })
      .bindPopup(() => locationPopup(feature), { maxWidth: 320 })
      .addTo(state.layers.locations);
  });
  const counts = features.reduce((result, feature) => {
    const type = feature.properties?.type;
    if (type) result[type] = (result[type] || 0) + 1;
    return result;
  }, {});
  const expected = { gram_panchayat: 70, municipality: 7, corporation: 1 };
  const plurals = {
    gram_panchayat: 'gram panchayats',
    municipality: 'municipalities',
    corporation: 'corporation',
  };
  const parts = Object.entries(expected).map(
    ([type, total]) => `${counts[type] || 0}/${total} ${plurals[type]}`,
  );
  state.locationStatus = features.length
    ? `Local-body centres: ${parts.join(' + ')}. Approximate area centres, not offices.`
    : 'Local-body centres unavailable: the locations file did not load.';
  if (has('location-coverage')) get('location-coverage').textContent = state.locationStatus;
  setLayerVisible(state.layers.locations, checked('layer-locations'));
}

function renderFacilities() {
  ['schools', 'hospitals'].forEach((key) => {
    if (state.layers[key]) state.map.removeLayer(state.layers[key]);
    state.layers[key] = L.layerGroup();
  });
  state.data.facilities.features.forEach((feature) => {
    const properties = feature.properties || {};
    const overlap = Boolean(properties[`overlap_${state.year}yr`]);
    const school = properties.kind === 'school';
    if (checked('only-overlap') && !overlap) return;
    if (!school && state.healthType && properties.healthcare_class !== state.healthType) return;
    const coordinates = feature.geometry.coordinates;
    const icon = L.divIcon({
      className: 'map-label',
      html: school
        ? `<span class="facility-square${overlap ? '' : ' facility-muted'}"></span>`
        : `<span class="facility-cross${overlap ? '' : ' facility-muted'}" aria-hidden="true"></span>`,
      iconSize: school ? [8, 8] : [17, 17],
      iconAnchor: school ? [4, 4] : [8, 8],
    });
    L.marker([coordinates[1], coordinates[0]], {
      icon,
      title: properties.name || healthClassLabel(properties),
      keyboard: true,
    })
      .bindPopup(() => facilityPopup(properties), { maxWidth: 310 })
      .addTo(state.layers[school ? 'schools' : 'hospitals']);
  });
  setLayerVisible(state.layers.schools, checked('layer-schools'));
  setLayerVisible(state.layers.hospitals, checked('layer-hospitals'));
}

function roadPopup(properties) {
  const status =
    properties.verification_status === 'official_directory_match'
      ? 'Matched to an official directory; this does not prove operating status or location accuracy.'
      : properties.verification_status === 'official_identity_unresolved'
        ? 'Official identity could not be resolved.'
        : 'Not independently checked.';
  return `${sourceEditMarkup(properties)}<h3>${escapeHtml(properties.name || 'Unnamed mapped major road')}</h3><p>${escapeHtml(properties.highway)} · ${escapeHtml(properties.osm_id)}</p><p>${formatDecimal(properties[`overlap_${state.year}yr_km`])} km of this record intersects the selected model footprint. Do not sum record lengths to reproduce the dissolved-network total.</p><p><strong>Record review:</strong> ${status} Roads remain unverified in the real world; no passability or flooding conclusion follows.</p><p>Bridge tag: ${escapeHtml(properties.bridge)}; tunnel tag: ${escapeHtml(properties.tunnel)}.</p>`;
}

function renderScenarioLayers() {
  ['model', 'roads'].forEach((key) => {
    if (state.layers[key]) state.map.removeLayer(state.layers[key]);
  });
  state.layers.model = L.geoJSON(state.flood[state.year], {
    style: { color: '#25859d', weight: 0.35, fillColor: '#4aaac1', fillOpacity: 0.42 },
    interactive: false,
    pane: 'model',
  });
  state.layers.roads = L.layerGroup();
  L.geoJSON(state.data.roads, {
    style: { color: '#b76518', weight: 1, opacity: 0.6 },
    pane: 'roads',
    onEachFeature: (feature, layer) => layer.bindPopup(() => roadPopup(feature.properties || {})),
  }).addTo(state.layers.roads);
  L.geoJSON(state.roadOverlaps[state.year], {
    style: { color: '#d46b22', weight: 2.6, opacity: 0.95 },
    interactive: false,
    pane: 'roads',
  }).addTo(state.layers.roads);
  setLayerVisible(state.layers.model, checked('layer-model'));
  setLayerVisible(state.layers.roads, checked('layer-roads'));
  renderFacilities();
  updateStats();
  renderLocalTable();
}

function fitMapTo(layerOrBounds, userInitiated = false) {
  if (!state.map || !layerOrBounds) return;
  const options = {
    padding: [18, 18],
    maxZoom: 13,
    animate: Boolean(userInitiated && !reducedMotion()),
  };
  if (options.animate) options.duration = 0.3;
  state.map.fitBounds(layerOrBounds, options);
}

function chooseScope(value, userInitiated = true, pushHistory = true) {
  state.scope = String(value || '');
  if (state.scope && !selectedLocalBody()) state.scope = '';
  if (has('local-select')) get('local-select').value = state.scope;
  if (state.layers.highlight) state.map.removeLayer(state.layers.highlight);
  if (state.scope) {
    const feature = state.data.localGeo.features.find(
      (item) => String(item.properties.id) === state.scope,
    );
    if (feature) {
      state.layers.highlight = L.geoJSON(feature, {
        style: { color: '#183d69', weight: 3, fillOpacity: 0.035 },
        interactive: false,
      }).addTo(state.map);
      fitMapTo(state.layers.highlight.getBounds(), userInitiated);
    }
  } else fitMapTo(state.bounds, userInitiated);
  state.page = 1;
  updateStats();
  renderLocalTable();
  if (pushHistory) writeUrlState(false);
}

function applyUrlState() {
  readUrlState();
  chooseScope(state.scope, false, false);
  renderScenarioLayers();
}

function compareRows(left, right, key, direction) {
  const factor = direction === 'ascending' ? 1 : -1;
  if (key === 'name' || key === 'type')
    return (
      String(left[key] || '').localeCompare(String(right[key] || ''), undefined, {
        sensitivity: 'base',
      }) * factor
    );
  const values = {
    schools: [`schools_overlap_${state.year}`],
    hospitals: [`hospitals_overlap_${state.year}`],
    roads: [`roads_overlap_km_${state.year}`],
  };
  return (Number(left[values[key]?.[0]] || 0) - Number(right[values[key]?.[0]] || 0)) * factor;
}

function localTypeLabel(type) {
  const labels = {
    gram_panchayat: 'Gram panchayat',
    municipality: 'Municipality',
    corporation: 'Corporation',
  };
  return labels[type] || String(type).replaceAll('_', ' ');
}

function renderLocalTable() {
  const body = get('local-rows');
  if (!body) return;
  const search = has('local-search') ? get('local-search').value.trim().toLocaleLowerCase() : '';
  const filtered = state.data.localRows.filter((row) =>
    `${row.name} ${row.type}`.toLocaleLowerCase().includes(search),
  );
  filtered.sort((left, right) => compareRows(left, right, state.sort, state.sortDirection));
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  state.page = Math.min(state.page, pageCount);
  const pageRows = filtered.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
  body.replaceChildren();
  pageRows.forEach((row) => {
    const tableRow = document.createElement('tr');
    const nameCell = document.createElement('td');
    const nameButton = document.createElement('button');
    nameButton.className = 'local-name';
    nameButton.type = 'button';
    nameButton.textContent = row.name;
    nameButton.addEventListener('click', () => {
      chooseScope(row.id);
      const map = get('map');
      if (map)
        map.scrollIntoView({ behavior: reducedMotion() ? 'auto' : 'smooth', block: 'center' });
    });
    nameCell.append(nameButton);
    tableRow.append(nameCell);
    [
      localTypeLabel(row.type),
      `${formatNumber(row[`schools_overlap_${state.year}`])} / ${formatNumber(row.schools_total)}`,
      `${formatNumber(row[`hospitals_overlap_${state.year}`])} / ${formatNumber(row.hospitals_total)}`,
      `${formatDecimal(row[`roads_overlap_km_${state.year}`])} / ${formatDecimal(row.roads_total_km)}`,
    ].forEach((text) => {
      const cell = document.createElement('td');
      cell.textContent = text;
      tableRow.append(cell);
    });
    body.append(tableRow);
  });
  if (!pageRows.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 5;
    cell.textContent = 'No local bodies match that search.';
    row.append(cell);
    body.append(row);
  }
  if (has('local-matches'))
    get('local-matches').textContent =
      `${filtered.length} matching local bod${filtered.length === 1 ? 'y' : 'ies'}`;
  if (has('local-page')) get('local-page').textContent = `Page ${state.page} of ${pageCount}`;
  if (has('local-prev')) get('local-prev').disabled = state.page <= 1;
  if (has('local-next')) get('local-next').disabled = state.page >= pageCount;
  document.querySelectorAll('[data-sort]').forEach((button) => {
    const active = button.dataset.sort === state.sort;
    const header = button.closest('th');
    button.removeAttribute('aria-sort');
    if (header) {
      if (active) header.setAttribute('aria-sort', state.sortDirection);
      else header.removeAttribute('aria-sort');
    }
  });
}

function downloadCsv(rows, filename) {
  if (!rows.length) return;
  const keys = Object.keys(rows[0]);
  const csvCell = (value) => {
    let text = value && typeof value === 'object' ? JSON.stringify(value) : String(value ?? '');
    if (typeof value === 'string' && /^[\s]*[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  };
  const headers = keys.map((key) => key.replace(/^hospitals_/, 'health_records_'));
  const content = `\ufeff${[headers.map(csvCell).join(','), ...rows.map((row) => keys.map((key) => csvCell(row[key])).join(','))].join('\r\n')}`;
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function showToast(message) {
  if (!has('toast')) return;
  get('toast').textContent = message;
  get('toast').hidden = false;
  window.setTimeout(() => {
    if (has('toast')) get('toast').hidden = true;
  }, 2800);
}

async function copyViewUrl() {
  const url = window.location.href;
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(url);
    showToast('View link copied.');
  } catch {
    const input = document.createElement('input');
    input.value = url;
    input.setAttribute('aria-label', 'View URL');
    document.body.append(input);
    input.select();
    try {
      if (!document.execCommand('copy')) throw new Error('Copy command failed');
      showToast('View link copied.');
    } catch {
      showToast('Copy is unavailable; the current URL is in the address bar.');
    }
    input.remove();
  }
}

function renderMetadata() {
  const metadata = state.data.metadata || {};
  const local = metadata.local_bodies || {};
  if (has('local-warning'))
    get('local-warning').textContent =
      local.short_note || 'Community boundary snapshot; see assignment and coverage notes below.';
  if (has('local-table-note'))
    get('local-table-note').textContent =
      local.table_note ||
      'Descriptive counts of mapped records. Mapping density, inventory size and boundary gaps affect comparisons; this is not a risk ranking.';
  const method = get('local-method');
  if (method) {
    method.replaceChildren();
    (local.method_paragraphs || []).forEach((text) => appendParagraph(method, text));
    if (state.data.unmatched)
      appendParagraph(
        method,
        `Unmatched coverage is retained in the original input summary (${formatDecimal(state.data.unmatched.roads_total_km)} km of mapped major roads) but is not a local body; district totals include it.`,
      );
    const summaryLink = document.createElement('p');
    summaryLink.append(
      safeSourceLink(
        `${DATA_ROOT}local_body_summary.json`,
        'Full input summary (including unmatched coverage)',
      ),
    );
    method.append(summaryLink);
    if (local.source_url) {
      const paragraph = document.createElement('p');
      paragraph.append(
        safeSourceLink(local.source_url, local.source_label || 'Local-body boundary source'),
      );
      method.append(paragraph);
    }
  }
  const review = metadata.inventory_review || {};
  if (has('inventory-review')) {
    const reviewElement = get('inventory-review');
    reviewElement.replaceChildren();
    if (!Object.keys(review).length) {
      appendParagraph(reviewElement, 'Inventory review metadata is not available yet.');
    } else {
      const labels = {
        facilities_status: 'School and health inventory',
        roads_status: 'Roads status',
        health_class_summary: 'Health types (OSM tags)',
        waterways_status: 'Waterway coverage',
        facilities_source_time: 'School and health snapshot dates',
        roads_source_time: 'Roads source date',
        official_checked: 'Facility identities reviewed',
        official_matches: 'Official-source identity matches',
        official_unresolved: 'Official identity unresolved',
        unreviewed: 'Not independently checked',
        quarantined: 'Records held out for review',
      };
      const definitionList = document.createElement('dl');
      Object.entries(labels).forEach(([key, label]) => {
        if (review[key] === undefined || review[key] === null || review[key] === '') return;
        const term = document.createElement('dt');
        term.textContent = label;
        const value = document.createElement('dd');
        value.textContent = String(review[key]);
        definitionList.append(term, value);
      });
      reviewElement.append(definitionList);
      appendParagraph(
        reviewElement,
        review.note || 'Source dates do not prove that every record is current.',
      );
      (review.sources || []).forEach((source) => {
        if (!source?.url) return;
        const paragraph = document.createElement('p');
        paragraph.append(safeSourceLink(source.url, source.label || 'Review source'));
        reviewElement.append(paragraph);
      });
    }
  }
  const observed = state.data.observed || {};
  if (has('observed-status')) {
    const status = get('observed-status');
    status.replaceChildren();
    appendParagraph(
      status,
      observed.available ? observed.title : 'No verified district-covering observed extent added.',
    );
    appendParagraph(
      status,
      observed.coverage_note ||
        observed.reason ||
        'No appropriate downloadable observation with verified Kozhikode coverage was accepted. Missing coverage is not evidence of dry land.',
    );
  }
  if (has('observed-method')) {
    const observedMethod = get('observed-method');
    observedMethod.replaceChildren();
    appendParagraph(observedMethod, observed.title || 'Observed inundation data review');
    ['event', 'observation_window', 'resolution', 'coverage_note'].forEach((field) => {
      if (observed[field])
        appendParagraph(observedMethod, `${field.replace(/_/g, ' ')}: ${observed[field]}`);
    });
    (Array.isArray(observed.limitations)
      ? observed.limitations
      : [observed.limitations].filter(Boolean)
    ).forEach((text) => appendParagraph(observedMethod, text));
    (observed.sources || []).forEach((source) => {
      const paragraph = document.createElement('p');
      paragraph.append(
        safeSourceLink(source.url || source.source_url, source.title || source.label),
      );
      observedMethod.append(paragraph);
    });
  }
  if (has('observed-caution'))
    get('observed-caution').textContent =
      'Observed event extents are not model scenarios. No accuracy or validation claim is inferred from visual agreement.';
  if (observed.available && state.layers.observed && has('observed-control')) {
    get('observed-control').hidden = false;
    get('observed-label').textContent = observed.title || 'Observed event extent';
  }
  if (state.layers.coverage && has('coverage-control')) get('coverage-control').hidden = false;
}

function buildScenarioTable() {
  const body = get('scenario-rows');
  if (!body) return;
  body.replaceChildren();
  state.data.summary.forEach((row) => {
    const tableRow = document.createElement('tr');
    tableRow.dataset.year = row.return_period_years;
    [
      `${row.return_period_years}-year`,
      `${row.annual_exceedance_probability_pct}%`,
      `${formatNumber(row.schools_overlap)} / ${formatNumber(row.schools_total_mapped)}`,
      `${formatNumber(row.hospitals_overlap)} / ${formatNumber(row.hospitals_total_mapped)}`,
      `${formatDecimal(row.major_roads_overlap_km)} / ${formatDecimal(row.major_roads_total_km)} km`,
    ].forEach((text) => {
      const cell = document.createElement('td');
      cell.textContent = text;
      tableRow.append(cell);
    });
    body.append(tableRow);
  });
}

function setContextStatus(message) {
  if (has('context-status')) get('context-status').textContent = message;
}

function updateContextStatus(context, errors = []) {
  if (errors.length) {
    setContextStatus(
      `Context unavailable: ${errors.join(' and ')}. Core map remains available; retry through reload.`,
    );
    return;
  }
  if (context?.terrain && context?.waterways)
    setContextStatus(
      `30 m surface relief · ${formatNumber(context.waterways.feature_count)} mapped waterways. Context only.`,
    );
}

function markContextFailure(kind, message) {
  const layer = state.layers[kind];
  if (layer && state.map?.hasLayer(layer)) state.map.removeLayer(layer);
  state.layers[kind] = null;
  setOptionalContextStatus(kind, message, true);
  window.contextReady = { ...(window.contextReady || {}), [kind]: false };
  window.contextErrors = [...new Set([...(window.contextErrors || []), kind])];
  updateContextStatus(
    null,
    window.contextErrors.map((item) => (item === 'terrain' ? 'terrain imagery' : 'waterways')),
  );
}

function setupContextLayers(context) {
  setContextStatus('Loading context…');
  if (!context || !state.map) {
    markContextFailure('terrain', 'Terrain imagery unavailable.');
    markContextFailure('waterways', 'Waterways unavailable.');
    updateContextStatus(null, ['terrain and waterways']);
    return;
  }
  state.map.createPane('context-terrain').style.zIndex = 250;
  state.map.createPane('context-waterways').style.zIndex = 280;
  window.contextReady = { terrain: false, waterways: false };
  state.layers.terrain =
    context.terrain?.bounds && context.terrain.image_url
      ? L.imageOverlay(context.terrain.image_url, context.terrain.bounds, {
          pane: 'context-terrain',
          opacity: 0.7,
          interactive: false,
        })
      : null;
  if (state.layers.terrain) {
    state.layers.terrain.once('load', () => {
      window.contextReady.terrain = true;
      setLayerVisible(state.layers.terrain, checked('layer-terrain'));
      if (window.contextReady.waterways) updateContextStatus(context);
    });
    state.layers.terrain.once('error', () =>
      markContextFailure('terrain', 'Terrain imagery failed to load.'),
    );
  } else markContextFailure('terrain', 'Terrain imagery unavailable.');
  state.layers.waterways = context.waterways?.file
    ? L.geoJSON(null, {
        pane: 'context-waterways',
        style: { color: '#4b91a8', weight: 1.2, opacity: 0.7 },
        interactive: false,
      })
    : null;
  if (state.layers.waterways)
    fetchJson(context.waterways.file.replace(/^data\//, ''))
      .then((geojson) => {
        if (!state.layers.waterways) return;
        state.layers.waterways.addData(geojson);
        setLayerVisible(state.layers.waterways, checked('layer-waterways'));
        window.contextReady.waterways = true;
        if (window.contextReady.terrain) updateContextStatus(context);
      })
      .catch(() => markContextFailure('waterways', 'Waterways failed to load.'));
  else markContextFailure('waterways', 'Waterways unavailable.');
  setLayerVisible(state.layers.terrain, checked('layer-terrain'));
  setLayerVisible(state.layers.waterways, checked('layer-waterways'));
}

function setupMap() {
  state.mapLocked =
    window.matchMedia?.('(pointer: coarse)').matches ||
    window.matchMedia?.('(max-width: 700px)').matches ||
    false;
  state.map = L.map('map', {
    preferCanvas: true,
    scrollWheelZoom: false,
    zoomControl: true,
    maxZoom: 18,
    zoomAnimation: !reducedMotion(),
    fadeAnimation: !reducedMotion(),
    markerZoomAnimation: !reducedMotion(),
    dragging: !state.mapLocked,
    touchZoom: !state.mapLocked,
  });
  const motionMedia = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  motionMedia?.addEventListener?.('change', (event) => {
    state.reducedMotion = event.matches;
    if (state.map) {
      state.map.options.zoomAnimation = !event.matches;
      state.map.options.fadeAnimation = !event.matches;
      state.map.options.markerZoomAnimation = !event.matches;
    }
  });
  state.map.createPane('land').style.zIndex = 220;
  state.map.createPane('context-terrain').style.zIndex = 250;
  state.map.createPane('context-waterways').style.zIndex = 280;
  state.map.createPane('model').style.zIndex = 350;
  state.map.createPane('roads').style.zIndex = 360;
  state.map.createPane('outline').style.zIndex = 410;
  L.geoJSON(state.data.district, {
    pane: 'land',
    style: { color: '#f8faf5', weight: 0, fillColor: '#f8faf5', fillOpacity: 1 },
    interactive: false,
  }).addTo(state.map);
  const outline = L.geoJSON(state.data.district, {
    pane: 'outline',
    style: { color: '#496671', weight: 1.7, fillOpacity: 0 },
    interactive: false,
  }).addTo(state.map);
  state.bounds = outline.getBounds();
  fitMapTo(state.bounds);
  L.control.scale({ imperial: false }).addTo(state.map);
  state.map.attributionControl.addAttribution(
    '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> · ODbL | KSDMA model',
  );
  state.layers.street = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap contributors',
  });
  state.layers.local = L.geoJSON(state.data.localGeo, {
    style: { color: '#6b8084', weight: 1, dashArray: '4 4', fillOpacity: 0 },
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(escapeHtml(feature.properties.name), { sticky: true });
      layer.on('click', () => chooseScope(feature.properties.id));
    },
  });
  state.layers.settlements = L.geoJSON(state.data.settlements, {
    pointToLayer: (feature, latlng) =>
      L.circleMarker(latlng, { radius: 2, color: '#294655', weight: 0, fillOpacity: 0.75 }),
    onEachFeature: (feature, layer) =>
      layer.bindPopup(
        `<h3>${escapeHtml(feature.properties.name || 'Unnamed settlement locator')}</h3><p>${escapeHtml(feature.properties.place)} · point locator only, not a settlement boundary or population-exposure measure.</p>`,
      ),
  });
  state.data.settlements.features
    .filter((feature) => ['city', 'town'].includes(feature.properties.place))
    .forEach((feature) => {
      const coordinates = feature.geometry.coordinates;
      L.marker([coordinates[1], coordinates[0]], {
        icon: L.divIcon({
          className: 'map-label',
          html: `<span class="settlement-label">${escapeHtml(feature.properties.name || '')}</span>`,
          iconSize: [120, 16],
          iconAnchor: [-3, 8],
        }),
        interactive: false,
      }).addTo(state.layers.settlements);
    });
  setLayerVisible(state.layers.local, checked('layer-local'));
  setLayerVisible(state.layers.settlements, checked('layer-settlements'));
  renderLocations();
  setupContextLayers(state.data.context);
}

function bindEvents() {
  if (state.eventsBound) return;
  state.eventsBound = true;
  if (has('health-type'))
    get('health-type').addEventListener('change', (event) => {
      state.healthType = event.target.value;
      renderFacilities();
      writeUrlState(true);
    });
  document.querySelectorAll('button[data-year]').forEach((button) =>
    button.addEventListener('click', () => {
      state.year = Number(button.dataset.year);
      state.page = 1;
      renderScenarioLayers();
      writeUrlState(false);
    }),
  );
  if (has('reset-map')) get('reset-map').addEventListener('click', () => chooseScope(''));
  if (has('local-select'))
    get('local-select').addEventListener('change', (event) => chooseScope(event.target.value));
  if (has('local-search'))
    get('local-search').addEventListener('input', () => {
      state.page = 1;
      renderLocalTable();
      writeUrlState(true);
    });
  if (has('local-prev'))
    get('local-prev').addEventListener('click', () => {
      state.page = Math.max(1, state.page - 1);
      renderLocalTable();
      writeUrlState(false);
    });
  if (has('local-next'))
    get('local-next').addEventListener('click', () => {
      state.page += 1;
      renderLocalTable();
      writeUrlState(false);
    });
  document.querySelectorAll('[data-sort]').forEach((button) =>
    button.addEventListener('click', () => {
      const sort = button.dataset.sort;
      state.sortDirection =
        state.sort === sort && state.sortDirection === 'ascending' ? 'descending' : 'ascending';
      state.sort = sort;
      state.page = 1;
      renderLocalTable();
      writeUrlState(true);
    }),
  );
  const layerControls = {
    model: 'model',
    schools: 'schools',
    hospitals: 'hospitals',
    roads: 'roads',
    settlements: 'settlements',
    local: 'local',
    terrain: 'terrain',
    waterways: 'waterways',
    observed: 'observed',
    coverage: 'coverage',
    locations: 'locations',
    street: 'street',
  };
  Object.entries(layerControls).forEach(([controlName, layerName]) => {
    if (has(`layer-${controlName}`))
      get(`layer-${controlName}`).addEventListener('change', () => {
        setLayerVisible(state.layers[layerName], checked(`layer-${controlName}`));
        if (['model', 'roads', 'schools', 'hospitals'].includes(layerName)) renderScenarioLayers();
        writeUrlState(true);
      });
  });
  if (has('only-overlap'))
    get('only-overlap').addEventListener('change', () => {
      renderFacilities();
      writeUrlState(true);
    });
  if (has('download-scenarios'))
    get('download-scenarios').addEventListener('click', () =>
      downloadCsv(state.data.summary, 'Kozhikode_scenario_comparison.csv'),
    );
  if (has('download-local'))
    get('download-local').addEventListener('click', () =>
      downloadCsv(state.data.localRows, 'Kozhikode_local_body_all_scenarios.csv'),
    );
  if (has('copy-view')) get('copy-view').addEventListener('click', copyViewUrl);
  if (has('unlock-map'))
    get('unlock-map').addEventListener('click', () => {
      state.mapLocked = !state.mapLocked;
      const button = get('unlock-map');
      if (state.mapLocked) state.map.dragging.disable();
      else state.map.dragging.enable();
      button.setAttribute('aria-pressed', String(!state.mapLocked));
      button.textContent = state.mapLocked ? 'Enable map dragging' : 'Pause map dragging';
      showToast(state.mapLocked ? 'Map dragging paused.' : 'Map dragging enabled.');
    });
  document.addEventListener('click', (event) => {
    const button = event.target.closest('.popup-select-local');
    if (button) {
      chooseScope(button.dataset.localId);
      state.map.closePopup();
    }
  });
  window.addEventListener('popstate', applyUrlState);
}

async function loadApplication() {
  if (state.dataPromise) return state.dataPromise;
  state.dataPromise = (async () => {
    updateLoadingControls(true);
    setLoadingProgress(0, 'Loading source layers…');
    LAYER_IDS.forEach((token) => {
      const control = get(`layer-${token}`);
      if (control) state.initialLayerDefaults[token] = control.checked;
    });
    const coreFiles = [
      'scenario_summary.json',
      'facilities.geojson',
      'roads.geojson',
      'settlements.geojson',
      'district.geojson',
      'local_body_summary.json',
      'local_bodies.geojson',
      'metadata.json',
      'observed_status.json',
    ];
    let completed = 0;
    const total = coreFiles.length + SCENARIOS.length * 2;
    const tracked = (promise) =>
      promise.then((data) => {
        completed += 1;
        setLoadingProgress(
          (completed / total) * 100,
          `Loaded ${completed} of ${total} model and asset files…`,
        );
        return data;
      });
    const corePromise = Promise.all(coreFiles.map((file) => tracked(fetchJson(file))));
    const scenarioPromise = Promise.all(
      SCENARIOS.flatMap((year) => [
        tracked(fetchJson(`flood_${year}.geojson`)),
        tracked(fetchJson(`road_overlap_${year}.geojson`)),
      ]),
    ).then((items) =>
      SCENARIOS.forEach((year, index) => {
        state.flood[year] = items[index * 2];
        state.roadOverlaps[year] = items[index * 2 + 1];
      }),
    );
    const contextPromise = fetchJson('context_metadata.json').catch(() => null);
    const locationsPromise = fetchJson('locations.geojson').catch(() => null);
    const [core] = await Promise.all([corePromise, scenarioPromise]);
    state.data.context = await contextPromise;
    state.data.locations = await locationsPromise;
    [
      state.data.summary,
      state.data.facilities,
      state.data.roads,
      state.data.settlements,
      state.data.district,
      state.data.localRows,
      state.data.localGeo,
      state.data.metadata,
      state.data.observed,
    ] = core;
    state.data.unmatched =
      state.data.localRows.find((row) => String(row.id) === 'UNMATCHED') || null;
    state.data.localRows = state.data.localRows.filter((row) => String(row.id) !== 'UNMATCHED');
    readUrlState();
    if (has('health-type')) {
      const select = get('health-type');
      const types = [
        ...new Set(
          state.data.facilities.features
            .filter((feature) => feature.properties.kind !== 'school')
            .map((feature) => feature.properties.healthcare_class),
        ),
      ]
        .filter(Boolean)
        .sort();
      types.forEach((type) => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = healthClassLabel({ healthcare_class: type });
        select.append(option);
      });
      select.value = state.healthType;
    }
    setupMap();
    state.data.localRows.forEach((row) => {
      if (has('local-select')) {
        const option = document.createElement('option');
        option.value = String(row.id);
        option.textContent = `${row.name} · ${localTypeLabel(row.type)}`;
        get('local-select').append(option);
      }
    });
    buildScenarioTable();
    if (state.data.observed.available) {
      try {
        const observedGeo = await fetchJson('observed_flood.geojson');
        state.layers.observed = L.geoJSON(observedGeo, {
          style: {
            color: '#243cbd',
            fillColor: '#8b9af0',
            fillOpacity: 0.28,
            weight: 2,
            dashArray: '6 3',
          },
          onEachFeature: (feature, layer) =>
            layer.bindPopup(
              `<h3>${escapeHtml(state.data.observed.title)}</h3><p>${escapeHtml(state.data.observed.observation_window || state.data.observed.event || '')}</p><p>${escapeHtml(state.data.observed.coverage_note || '')}</p><p>Separate observed event layer—not a return-period scenario.</p>`,
            ),
        });
      } catch {
        state.layers.observed = null;
      }
    }
    if (state.data.observed.has_coverage) {
      try {
        state.layers.coverage = L.geoJSON(await fetchJson('observed_coverage.geojson'), {
          style: { color: '#243cbd', fillOpacity: 0, weight: 1.5, dashArray: '2 6' },
        });
      } catch {
        state.layers.coverage = null;
      }
    }
    renderMetadata();
    renderScenarioLayers();
    bindEvents();
    if (state.scope) chooseScope(state.scope, false, false);
    if (has('unlock-map')) {
      const button = get('unlock-map');
      button.hidden = !(
        window.matchMedia?.('(pointer: coarse)').matches ||
        window.matchMedia?.('(max-width: 700px)').matches
      );
      button.setAttribute('aria-pressed', String(!state.mapLocked));
      button.textContent = state.mapLocked ? 'Enable map dragging' : 'Pause map dragging';
    }
    setLoadingProgress(100, 'Ready');
    updateLoadingControls(false);
    if (has('map-loading')) get('map-loading').hidden = true;
    window.appReady = true;
    writeUrlState(true);
  })();
  return state.dataPromise;
}

function showLoadError(error) {
  const message = `The explorer could not finish loading its data. Check your connection and try again. ${error.message}`;
  if (has('load-error')) {
    const errorElement = get('load-error');
    errorElement.hidden = false;
    errorElement.textContent = message;
  }
  if (has('load-message')) get('load-message').textContent = message;
  if (has('map-status')) get('map-status').textContent = 'Data failed to load';
  if (has('map-loading')) get('map-loading').hidden = false;
  if (has('retry-load')) {
    get('retry-load').hidden = false;
    get('retry-load').disabled = false;
  }
  window.appError = error.message;
  updateLoadingControls(true);
}

function start() {
  window.appReady = false;
  window.appError = '';
  if (has('retry-load'))
    get('retry-load').addEventListener('click', () => window.location.reload());
  loadApplication().catch(showLoadError);
}

start();
