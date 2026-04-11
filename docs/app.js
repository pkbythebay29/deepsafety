const apiBaseInput = document.getElementById("apiBaseUrl");
const saveApiBaseButton = document.getElementById("saveApiBase");
const mapUploadInput = document.getElementById("mapUpload");
const scenarioTypeSelect = document.getElementById("scenarioType");
const modelIdSelect = document.getElementById("modelId");
const scenarioFields = document.getElementById("scenarioFields");
const constantOverrides = document.getElementById("constantOverrides");
const runScenarioButton = document.getElementById("runScenario");
const runImpactZonesButton = document.getElementById("runImpactZones");
const sourceModeButton = document.getElementById("sourceMode");
const receptorModeButton = document.getElementById("receptorMode");
const resetMapButton = document.getElementById("resetMap");
const resultsContainer = document.getElementById("results");
const modelDocsContainer = document.getElementById("modelDocs");

const storedApiBase =
  window.localStorage.getItem("deepsafety-api-base") || "http://127.0.0.1:8000";
apiBaseInput.value = storedApiBase;

const state = {
  mapMode: "source",
  source: null,
  sourceMarker: null,
  receptorMarkers: [],
  zoneLayers: [],
  overlayLayer: null,
  modelsByScenario: {},
};

const map = L.map("map", { zoomControl: false }).setView([51.505, -0.09], 5);
L.control.zoom({ position: "topright" }).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

function apiBase() {
  return apiBaseInput.value.replace(/\/$/, "");
}

function setStatus(message) {
  resultsContainer.innerHTML = `<div class="status">${message}</div>`;
}

function getScenarioConfig(type) {
  if (type === "fire") {
    return [
      { key: "burning_rate_kg_s", label: "Burning rate (kg/s)", value: "4.5" },
      { key: "heat_of_combustion_kj_kg", label: "Heat of combustion (kJ/kg)", value: "46000" },
      { key: "impact_threshold_kw_m2", label: "Impact threshold (kW/m^2)", value: "12.5" },
    ];
  }

  return [
    { key: "line_pressure_kpa", label: "Line pressure (kPa)", value: "6000" },
    { key: "mass_flow_kg_s", label: "Gas flow (kg/s)", value: "1.2" },
    { key: "gas_temperature_c", label: "Gas temperature (degC)", value: "18" },
    { key: "leak_duration_s", label: "Leak duration (s)", value: "60" },
    { key: "stability_class", label: "Stability class (A-F)", value: "D" },
    { key: "impact_threshold_kg_m3", label: "Concern threshold (kg/m^3)", value: "0.02" },
    { key: "Q", label: "Optional receptor screening release mass (kg)", value: "25" },
    { key: "u", label: "Optional receptor screening wind speed (m/s)", value: "3.5" },
  ];
}

function renderScenarioFields() {
  const fields = getScenarioConfig(scenarioTypeSelect.value);
  scenarioFields.innerHTML = fields
    .map(
      (field) => `
        <label class="field">
          <span>${field.label}</span>
          <input data-input-key="${field.key}" value="${field.value}" />
        </label>
      `,
    )
    .join("");
}

function clearZoneLayers() {
  state.zoneLayers.forEach((layer) => map.removeLayer(layer));
  state.zoneLayers = [];
}

function resetMapState() {
  state.source = null;
  if (state.sourceMarker) {
    map.removeLayer(state.sourceMarker);
    state.sourceMarker = null;
  }
  state.receptorMarkers.forEach((marker) => map.removeLayer(marker));
  state.receptorMarkers = [];
  clearZoneLayers();
  setStatus("Map reset. Place a source pin to begin.");
}

function addReceptorMarker(latlng) {
  const marker = L.circleMarker(latlng, {
    radius: 8,
    weight: 2,
    color: "#143642",
    fillColor: "#ea6a47",
    fillOpacity: 0.85,
  }).addTo(map);
  marker.bindPopup(`Receptor ${state.receptorMarkers.length + 1}`);
  state.receptorMarkers.push(marker);
}

map.on("click", (event) => {
  if (state.mapMode === "source") {
    if (state.sourceMarker) {
      map.removeLayer(state.sourceMarker);
    }
    clearZoneLayers();
    state.source = event.latlng;
    state.sourceMarker = L.marker(event.latlng).addTo(map);
    state.sourceMarker.bindPopup("Source").openPopup();
    setStatus("Source set. Switch to receptor mode to add points or draw an impact circle.");
    return;
  }

  addReceptorMarker(event.latlng);
  setStatus(`Added receptor ${state.receptorMarkers.length}. You can keep dropping pins or run the scenario.`);
});

function saveApiBase() {
  window.localStorage.setItem("deepsafety-api-base", apiBase());
  setStatus(`Saved API base URL: ${apiBase()}`);
  hydrateScenarioModels();
}

async function fetchJson(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  return response.json();
}

async function hydrateScenarioModels() {
  try {
    const scenarios = await fetchJson("/scenarios");
    state.modelsByScenario = scenarios;
    populateModels();
  } catch (error) {
    setStatus(`Unable to reach API: ${error.message}`);
  }
}

function populateModels() {
  const scenario = state.modelsByScenario[scenarioTypeSelect.value];
  if (!scenario) {
    modelIdSelect.innerHTML = "";
    return;
  }

  modelIdSelect.innerHTML = scenario.models
    .filter((model) => model.status === "implemented")
    .map(
      (model) =>
        `<option value="${model.id}" ${model.id === scenario.default_model_id ? "selected" : ""}>${model.name}</option>`,
    )
    .join("");

  renderModelDocs();
}

function parseInputs() {
  const inputs = {};
  scenarioFields.querySelectorAll("[data-input-key]").forEach((input) => {
    const key = input.dataset.inputKey;
    const rawValue = input.value.trim();
    const numericValue = Number(rawValue);
    inputs[key] = Number.isNaN(numericValue) ? rawValue : numericValue;
  });
  return inputs;
}

function parseConstants() {
  const raw = constantOverrides.value.trim();
  if (!raw) {
    return {};
  }
  return JSON.parse(raw);
}

function receptorsPayload() {
  return state.receptorMarkers.map((marker, index) => ({
    id: `receptor-${index + 1}`,
    label: `Receptor ${index + 1}`,
    latitude: marker.getLatLng().lat,
    longitude: marker.getLatLng().lng,
  }));
}

function renderResultsMarkup(cards) {
  resultsContainer.innerHTML = cards.join("");
}

async function renderModelDocs() {
  const modelId = modelIdSelect.value;
  if (!modelId) {
    modelDocsContainer.innerHTML = "";
    return;
  }

  try {
    const model = await fetchJson(`/models/${modelId}`);
    const equations = model.equations.map((equation) => `<li>${equation}</li>`).join("");
    const constants = model.constants
      .map(
        (constant) =>
          `<li>${constant.name}: <strong>${constant.value}</strong> ${constant.unit}</li>`,
      )
      .join("");
    modelDocsContainer.innerHTML = `
      <article class="doc-card">
        <h3>${model.name}</h3>
        <p class="result-meta">${model.summary}</p>
        <h4>Equations</h4>
        <ul class="equation-list">${equations || "<li>No equations documented yet.</li>"}</ul>
        <h4>Default constants</h4>
        <ul class="constant-list">${constants || "<li>No model constants.</li>"}</ul>
      </article>
    `;
  } catch (error) {
    modelDocsContainer.innerHTML = `<div class="status">${error.message}</div>`;
  }
}

function renderZoneLayers(payload) {
  clearZoneLayers();
  payload.geojson.features
    .filter((feature) => feature.geometry.type === "Polygon")
    .forEach((feature, index) => {
      const layer = L.geoJSON(feature, {
        style: {
          color: index % 2 === 0 ? "#ea6a47" : "#143642",
          weight: 2,
          fillOpacity: 0.14,
        },
      }).addTo(map);
      state.zoneLayers.push(layer);
    });
}

async function runScenario() {
  if (!state.source) {
    setStatus("Place a source pin first.");
    return;
  }

  try {
    const formInputs = parseInputs();
    const payload = {
      scenario_type: scenarioTypeSelect.value,
      model_id: modelIdSelect.value,
      source: {
        latitude: state.source.lat,
        longitude: state.source.lng,
        label: "Source",
      },
      receptors: receptorsPayload(),
      inputs:
        scenarioTypeSelect.value === "fire"
          ? {
              burning_rate_kg_s: formInputs.burning_rate_kg_s,
              heat_of_combustion_kj_kg: formInputs.heat_of_combustion_kj_kg,
            }
          : {
              Q: formInputs.Q,
              u: formInputs.u,
              stability_class: formInputs.stability_class,
            },
      constants: parseConstants(),
    };

    const result = await fetchJson("/gis/scenarios/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!result.receptors.length) {
      setStatus("No receptor pins were provided.");
      return;
    }

    renderResultsMarkup(
      result.receptors.map((receptor) => {
        const outputRows = Object.entries(receptor.outputs)
          .map(([key, value]) => `<li>${key}: <strong>${value}</strong></li>`)
          .join("");
        return `
          <article class="result-card">
            <h3>${receptor.label || receptor.id}</h3>
            <p class="result-meta">Distance: ${receptor.distance_m} m</p>
            <ul class="result-meta">${outputRows}</ul>
          </article>
        `;
      }),
    );
    renderModelDocs();
  } catch (error) {
    setStatus(`Scenario run failed: ${error.message}`);
  }
}

async function runImpactZones() {
  if (!state.source) {
    setStatus("Place a source pin first.");
    return;
  }

  try {
    const formInputs = parseInputs();
    const payload =
      scenarioTypeSelect.value === "fire"
        ? {
            scenario_type: "fire",
            source: {
              latitude: state.source.lat,
              longitude: state.source.lng,
              label: "Source",
            },
            asset: {
              burning_rate_kg_s: formInputs.burning_rate_kg_s,
              heat_of_combustion_kj_kg: formInputs.heat_of_combustion_kj_kg,
            },
            criteria: [
              {
                label: "Thermal impact threshold",
                threshold: formInputs.impact_threshold_kw_m2,
                unit: "kW/m^2",
              },
            ],
            constants: parseConstants(),
          }
        : {
            scenario_type: "leak",
            source: {
              latitude: state.source.lat,
              longitude: state.source.lng,
              label: "Gas line segment",
            },
            asset: {
              line_pressure_kpa: formInputs.line_pressure_kpa,
              mass_flow_kg_s: formInputs.mass_flow_kg_s,
              gas_temperature_c: formInputs.gas_temperature_c,
              leak_duration_s: formInputs.leak_duration_s,
              stability_class: formInputs.stability_class,
            },
            criteria: [
              {
                label: "Concern threshold",
                threshold: formInputs.impact_threshold_kg_m3,
                unit: "kg/m^3",
              },
            ],
            constants: parseConstants(),
          };

    const result = await fetchJson("/gis/impact-zones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    renderZoneLayers(result);
    renderResultsMarkup(
      result.zones.map(
        (zone) => `
          <article class="result-card">
            <h3>${zone.label}</h3>
            <p class="result-meta">Radius: ${zone.radius_m.toFixed(2)} m</p>
            <p class="result-meta">Area: ${zone.area_m2.toFixed(2)} m²</p>
            <p class="result-meta">Threshold: ${zone.threshold} ${zone.unit}</p>
          </article>
        `,
      ),
    );
  } catch (error) {
    setStatus(`Impact-zone run failed: ${error.message}`);
  }
}

function handleMapUpload(event) {
  const [file] = event.target.files || [];
  if (!file) {
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    if (state.overlayLayer) {
      map.removeLayer(state.overlayLayer);
    }
    state.overlayLayer = L.imageOverlay(reader.result, map.getBounds(), {
      opacity: 0.55,
    }).addTo(map);
    setStatus("Custom map overlay loaded over the current view.");
  };
  reader.readAsDataURL(file);
}

saveApiBaseButton.addEventListener("click", saveApiBase);
mapUploadInput.addEventListener("change", handleMapUpload);
scenarioTypeSelect.addEventListener("change", () => {
  renderScenarioFields();
  populateModels();
});
modelIdSelect.addEventListener("change", renderModelDocs);
runScenarioButton.addEventListener("click", runScenario);
runImpactZonesButton.addEventListener("click", runImpactZones);
sourceModeButton.addEventListener("click", () => {
  state.mapMode = "source";
  setStatus("Source placement mode enabled.");
});
receptorModeButton.addEventListener("click", () => {
  state.mapMode = "receptor";
  setStatus("Receptor placement mode enabled.");
});
resetMapButton.addEventListener("click", resetMapState);

renderScenarioFields();
hydrateScenarioModels();
setStatus("Place a source pin, configure the asset, and draw an impact circle.");
