const apiBaseInput = document.getElementById("apiBaseUrl");
const saveApiBaseButton = document.getElementById("saveApiBase");
const mapUploadInput = document.getElementById("mapUpload");
const signPhotoInput = document.getElementById("signPhoto");
const signObservedTextInput = document.getElementById("signObservedText");
const analyzeSignButton = document.getElementById("analyzeSign");
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
  window.localStorage.getItem("deepsafety-api-base") ||
  window.DeepSafetyBrowserApi?.defaultBaseUrl ||
  "browser://local";
apiBaseInput.value = storedApiBase;

const state = {
  mapMode: "source",
  source: null,
  sourceMarker: null,
  receptorMarkers: [],
  zoneLayers: [],
  overlayLayer: null,
  modelsByScenario: {},
  signPhotoDataUrl: null,
};

const map = L.map("map", { zoomControl: false }).setView([51.505, -0.09], 5);
L.control.zoom({ position: "topright" }).addTo(map);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

function apiBase() {
  return apiBaseInput.value.replace(/\/$/, "");
}

function isBrowserLocalMode() {
  return apiBase().startsWith("browser://");
}

function setStatus(message) {
  resultsContainer.innerHTML = `<div class="status">${message}</div>`;
}

function getScenarioConfig(type) {
  if (type === "fire") {
    return [
      {
        key: "burning_rate_kg_s",
        label: "Burning rate (kg/s)",
        value: "4.5",
        help: "Mass burning rate used by the fire radiation model.",
      },
      {
        key: "heat_of_combustion_kj_kg",
        label: "Heat of combustion (kJ/kg)",
        value: "46000",
        help: "Energy released per kilogram of fuel burned.",
      },
      {
        key: "impact_threshold_kw_m2",
        label: "Impact threshold (kW/m^2)",
        value: "12.5",
        help: "Thermal radiation threshold used to draw the impact circle.",
      },
    ];
  }

  return [
    {
      key: "line_pressure_kpa",
      label: "Line pressure (kPa)",
      value: "6000",
      help: "Internal line pressure used to estimate gas release if a leak occurs.",
    },
    {
      key: "gas_temperature_c",
      label: "Gas temperature (degC)",
      value: "18",
      help: "Gas temperature at release conditions.",
    },
    {
      key: "diameter_m",
      label: "Line diameter (m)",
      value: "0.015",
      help: "Pipe or release connection diameter used in the source-term model.",
    },
    {
      key: "hole_diameter_m",
      label: "Leak hole diameter (m)",
      value: "0.005",
      help: "Estimated opening size for the leak itself.",
    },
    {
      key: "pipe_length_m",
      label: "Pipe length to source (m)",
      value: "30",
      help: "Used for simple friction-limited pipe discharge screening.",
    },
    {
      key: "molecular_weight_kg_kmol",
      label: "Molecular weight (kg/kmol)",
      value: "28.97",
      help: "Used to derive the gas constant for source-term calculations.",
    },
    {
      key: "heat_capacity_ratio",
      label: "Heat capacity ratio",
      value: "1.3",
      help: "Specific heat ratio used for choked and non-choked gas discharge screening.",
    },
    {
      key: "leak_duration_s",
      label: "Leak duration (s)",
      value: "60",
      help: "Duration before isolation, depletion, or intervention.",
    },
    {
      key: "stability_class",
      label: "Stability class (A-F)",
      value: "D",
      help: "Atmospheric stability class used for dispersion screening.",
    },
    {
      key: "impact_threshold_kg_m3",
      label: "Concern threshold (kg/m^3)",
      value: "0.02",
      help: "Concentration threshold used to draw the leak impact circle.",
    },
    {
      key: "Q",
      label: "Receptor screening release mass (kg)",
      value: "25",
      help: "Optional direct released mass used for receptor screening in the puff model.",
    },
    {
      key: "u",
      label: "Receptor screening wind speed (m/s)",
      value: "3.5",
      help: "Wind speed used for receptor concentration screening.",
    },
  ];
}

function renderScenarioFields() {
  const fields = getScenarioConfig(scenarioTypeSelect.value);
  scenarioFields.innerHTML = fields
    .map(
      (field) => `
        <label class="field">
          <span class="field-label-row">
            <span>${field.label}</span>
            <span class="info-badge" title="${field.help.replace(/"/g, "&quot;")}">?</span>
          </span>
          <input data-input-key="${field.key}" value="${field.value}" />
          <small class="field-help">${field.help}</small>
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
  if (isBrowserLocalMode()) {
    const body = options.body ? JSON.parse(options.body) : undefined;
    return window.DeepSafetyBrowserApi.request(options.method || "GET", path, body);
  }
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
    const equationTooltip =
      model.equations.length > 0 ? model.equations.join(" | ") : "No equations documented.";
    const constantTooltip =
      model.constants.length > 0
        ? model.constants
            .map(
              (constant) =>
                `${constant.name} = ${constant.value} ${constant.unit}; ${constant.description}; source=${constant.source}`,
            )
            .join(" | ")
        : "No constants documented.";
    const referenceTooltip =
      model.references && model.references.length > 0
        ? model.references
            .map((reference) => `${reference.title}${reference.notes ? `: ${reference.notes}` : ""}`)
            .join(" | ")
        : "Source references are not listed for this model yet.";
    const equations = model.equations.map((equation) => `<li>${equation}</li>`).join("");
    const constants = model.constants
      .map(
        (constant) =>
          `<li>${constant.name}: <strong>${constant.value}</strong> ${constant.unit} - ${constant.description} (${constant.source})</li>`,
      )
      .join("");
    const references =
      model.references && model.references.length > 0
        ? model.references
            .map(
              (reference) =>
                `<li>${reference.title}${reference.notes ? ` - ${reference.notes}` : ""}${reference.url ? ` (<a href="${reference.url}" target="_blank" rel="noreferrer">link</a>)` : ""}</li>`,
            )
            .join("")
        : "<li>No explicit references listed for this model yet.</li>";
    modelDocsContainer.innerHTML = `
      <article class="doc-card">
        <h3>${model.name}</h3>
        <p class="result-meta">${model.summary}</p>
        <div class="detail-chip-row">
          <span class="detail-chip" title="${equationTooltip.replace(/"/g, "&quot;")}">Equation details</span>
          <span class="detail-chip" title="${constantTooltip.replace(/"/g, "&quot;")}">Constant details</span>
          <span class="detail-chip" title="${referenceTooltip.replace(/"/g, "&quot;")}">Data source details</span>
        </div>
        <h4>Equations</h4>
        <ul class="equation-list">${equations || "<li>No equations documented yet.</li>"}</ul>
        <h4>Default constants</h4>
        <ul class="constant-list">${constants || "<li>No model constants.</li>"}</ul>
        <h4>References</h4>
        <ul class="reference-list">${references}</ul>
      </article>
    `;
  } catch (error) {
    modelDocsContainer.innerHTML = `<div class="status">${error.message}</div>`;
  }
}

function renderZoneLayers(payload) {
  clearZoneLayers();
  const palette = ["#8b0000", "#ea6a47", "#ffb703", "#2a9d8f"];
  payload.geojson.features
    .filter((feature) => feature.geometry.type === "Polygon")
    .forEach((feature, index) => {
      const layer = L.geoJSON(feature, {
        style: {
          color: palette[index % palette.length],
          weight: 2,
          fillOpacity: 0.18,
        },
      }).addTo(map);
      if (feature.properties && feature.properties.label) {
        layer.bindTooltip(
          `${feature.properties.label}: ${Number(feature.properties.radius_m || 0).toFixed(1)} m`,
          { sticky: true },
        );
      }
      state.zoneLayers.push(layer);
    });
}

function leakCriteria(threshold) {
  return [
    {
      label: "Severe consequence ring",
      threshold: threshold * 3,
      unit: "kg/m^3",
      effect: "Severe acute exposure screening zone",
    },
    {
      label: "Primary consequence ring",
      threshold,
      unit: "kg/m^3",
      effect: "Primary concern screening zone",
    },
    {
      label: "Awareness ring",
      threshold: threshold * 0.3,
      unit: "kg/m^3",
      effect: "Extended awareness and planning zone",
    },
  ];
}

function fireCriteria(threshold) {
  return [
    {
      label: "Severe thermal ring",
      threshold: Math.max(threshold * 2.5, threshold + 10),
      unit: "kW/m^2",
      effect: "High lethality thermal exposure screening zone",
    },
    {
      label: "Primary thermal ring",
      threshold,
      unit: "kW/m^2",
      effect: "Primary burn and escalation screening zone",
    },
    {
      label: "Cautionary thermal ring",
      threshold: Math.max(threshold * 0.32, 4),
      unit: "kW/m^2",
      effect: "Lower-intensity thermal exposure screening zone",
    },
  ];
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
            criteria: fireCriteria(formInputs.impact_threshold_kw_m2),
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
              gas_temperature_c: formInputs.gas_temperature_c,
              diameter_m: formInputs.diameter_m,
              hole_diameter_m: formInputs.hole_diameter_m,
              pipe_length_m: formInputs.pipe_length_m,
              molecular_weight_kg_kmol: formInputs.molecular_weight_kg_kmol,
              heat_capacity_ratio: formInputs.heat_capacity_ratio,
              leak_duration_s: formInputs.leak_duration_s,
              stability_class: formInputs.stability_class,
            },
            criteria: leakCriteria(formInputs.impact_threshold_kg_m3),
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
        (zone, index) => `
          <article class="result-card">
            <h3>Ring ${index + 1}: ${zone.label}</h3>
            <p class="result-meta">Radius: ${zone.radius_m.toFixed(2)} m</p>
            <p class="result-meta">Area: ${zone.area_m2.toFixed(2)} m^2</p>
            <p class="result-meta">Threshold: ${zone.threshold} ${zone.unit}</p>
            <p class="result-meta">Effect meaning: ${(payload.criteria[index] && payload.criteria[index].effect) || "Consequence screening ring"}</p>
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

function handleSignPhotoUpload(event) {
  const [file] = event.target.files || [];
  if (!file) {
    state.signPhotoDataUrl = null;
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    state.signPhotoDataUrl = reader.result;
    setStatus("Sign photo loaded. Add sign text or OCR and run sign analysis.");
  };
  reader.readAsDataURL(file);
}

async function analyzeSign() {
  try {
    const payload = {
      observed_text: signObservedTextInput.value.trim(),
      site_context: "map workflow",
      topography: "urban",
      stability_class: parseInputs().stability_class || "D",
      wind_speed_m_s: parseInputs().u || 3.0,
    };
    if (state.signPhotoDataUrl) {
      const [header, base64] = String(state.signPhotoDataUrl).split(",", 2);
      payload.image_base64 = base64 || "";
      payload.image_media_type = header?.match(/data:(.*?);base64/)?.[1] || "image/jpeg";
    }

    const result = await fetchJson("/signs/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (result.scenario_template_id === "pipeline_leak") {
      scenarioTypeSelect.value = "leak";
      renderScenarioFields();
      populateModels();
    }

    renderResultsMarkup([
      `
        <article class="result-card">
          <h3>Sign analysis</h3>
          <p class="result-meta">Type: ${result.sign_type}</p>
          <p class="result-meta">Confidence: ${result.confidence}</p>
          <p class="result-meta">Asset: ${result.asset_type}</p>
          <p class="result-meta">Hazards: ${result.hazard_classes.join(", ")}</p>
          <p class="result-meta">Matched terms: ${result.matched_terms.join(", ") || "none"}</p>
          <p class="result-meta">Next inputs: ${result.required_parameters.map((item) => item.name).join(", ")}</p>
        </article>
      `,
    ]);
    setStatus("Sign analyzed. You can now complete the seeded leak scenario inputs and run the impact circle.");
  } catch (error) {
    setStatus(`Sign analysis failed: ${error.message}`);
  }
}

saveApiBaseButton.addEventListener("click", saveApiBase);
mapUploadInput.addEventListener("change", handleMapUpload);
signPhotoInput.addEventListener("change", handleSignPhotoUpload);
analyzeSignButton.addEventListener("click", analyzeSign);
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
setStatus("Place a source pin, configure the asset, or analyze a sign photo to seed a leak scenario.");
