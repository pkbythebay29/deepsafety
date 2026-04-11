# DeepSafety
**DeepSafety** is an open-source process safety analysis platform packaged as one Python install target, one FastAPI service, one MCP bridge, and one browser-local runtime for GitHub Pages.

## Modeling Chain

The API is organized around the actual modeling chain:

1. `materials` and operating/design data define the upstream physical and toxicological basis.
2. `scenario-engine` and `source-models` define realistic, worst-case, and conservative releases.
3. `dispersion` and `effect-models` translate the source term into concentration, radiation, blast, and human-impact outputs.
4. `hazard-evaluation` workflows use those outputs in HAZOP, FMEA, What-If, checklist, and related studies.

That structure is important: source-term outputs are meant to feed dispersion, and dispersion/effect outputs are meant to feed scenario-based hazard studies rather than live as disconnected calculators.

## Implemented API Capabilities

- Foundational material records with physical properties, toxicity, flammability, and reactivity starter data
- Scenario definition and scenario-library templates for realistic-case, worst-case, and conservative-analysis workflows
- Source models for gas/vapor release, liquid release, flashing, pool formation, and evaporation
- Dispersion models for Gaussian plume, Gaussian puff, dense-gas screening, isopleths, toxic-endpoint evaluation, and mitigation-adjusted releases
- Fire and explosion models for flammability mixtures, LOC, ignition energy, jet fire, pool fire, fireball/BLEVE, TNT equivalency, multi-energy, VCE, deflagration, detonation, blast damage, and mitigation screening
- Health and industrial-hygiene utilities for concentration conversion, probit evaluation, TWA, exposure compliance, ventilation, and pool evaporation
- Prevention, reactivity, and relief-system endpoints for purging, static electricity, area classification, fire protection, calorimetry interpretation, reactivity screening/control, relief selection, and relief sizing
- Hazard-evaluation workflows for checklist, safety review, inherent safety review, preliminary hazard analysis, relative ranking, HAZOP, FMEA, What-If, What-If/Checklist, and information-requirement validation
- Visualization, GIS, sign-intelligence, MCP, Docker, browser-local, and Jupyter integration surfaces

## Data Provenance

- Starter material records are packaged in `deepsafety/data/materials_registry.json`
- Starter toxic criteria are packaged in `deepsafety/data/toxic_criteria_registry.json`
- Shared physical constants and screening defaults are packaged in `deepsafety/data/constants_registry.json`

Material properties are not embedded directly in Python code. The packaged registries are the source of truth for starter data, and each registry includes provenance notes so the origin and intended use are explicit.

## License
This project is licensed under the MIT License. 

## Contributing

Contributions are welcome. Please fork the repository, open a pull request, and include tests for any new functionality.

## API Surface

The HTTP service now exposes:

- `GET /models`, `GET /models/{model_id}`, `POST /models/{model_id}/calculate`
- `GET /constants`, `GET /constants/{model_id}`, `GET /service-catalog`
- `GET /materials`, `GET /materials/{materialId}`, `GET /materials/{materialId}/toxicity`, `GET /materials/{materialId}/flammability`, `GET /materials/{materialId}/reactivity`
- `POST /health/convert-concentration`, `POST /health/probit/evaluate`, `POST /health/exposure/twa`, `POST /health/exposure/compliance`
- `POST /industrial-hygiene/ventilation/dilution`, `POST /industrial-hygiene/ventilation/local-exhaust`, `POST /industrial-hygiene/liquid-pool/evaporation`
- `POST /scenario-engine/define`, `GET /scenario-library/templates`
- `POST /source-models/liquid-hole`, `POST /source-models/tank-hole`, `POST /source-models/liquid-pipe`, `POST /source-models/gas-hole`, `POST /source-models/gas-pipe`, `POST /source-models/flashing-liquid`, `POST /source-models/scenario/select`, `POST /source-models/conservative-analysis`
- `POST /dispersion/gaussian-plume`, `POST /dispersion/gaussian-puff`, `POST /dispersion/dense-gas`, `POST /dispersion/isopleth`, `POST /dispersion/toxic-endpoints/evaluate`, `POST /dispersion/prevention-mitigation`
- `POST /fire-explosion/flammability/mixture`, `POST /fire-explosion/loc`, `POST /fire-explosion/ignition-energy`, `POST /fire-explosion/tnt-equivalency`, `POST /fire-explosion/multi-energy`, `POST /fire-explosion/vce`, `POST /fire-explosion/bleve`
- `POST /prevention/inerting/purge`, `POST /prevention/static-electricity/risk`, `POST /prevention/area-classification`, `POST /prevention/fire-protection/strategy`
- `POST /reactivity/calorimetry/interpret`, `POST /reactivity/screening`, `POST /reactivity/control`
- `POST /relief/devices/select`, `POST /relief/system/analyze`, `POST /relief/effluent-handling/select`, `POST /relief/sizing/liquid`, `POST /relief/sizing/gas-vapor`, `POST /relief/sizing/two-phase`, `POST /relief/sizing/deflagration-vent`, `POST /relief/sizing/external-fire`, `POST /relief/sizing/thermal-expansion`
- `POST /hazard-evaluation/checklist`, `POST /hazard-evaluation/safety-review`, `POST /hazard-evaluation/inherent-safety-review`, `POST /hazard-evaluation/preliminary-hazard-analysis`, `POST /hazard-evaluation/relative-ranking`, `POST /hazard-evaluation/hazop`, `POST /hazard-evaluation/fmea`, `POST /hazard-evaluation/what-if`, `POST /hazard-evaluation/what-if-checklist`, `POST /hazard-evaluation/information-requirements/validate`
- `POST /effect-models/solve`, `POST /toxic-criteria/lookup`, `POST /prevention-response-models/solve`, `POST /visualization/solve`, `POST /signs/analyze`, `POST /gis/scenarios/evaluate`, `POST /gis/impact-zones`

Each model documents the equations used and the constants applied in the response itself.

## Implemented Service Layers

### Scenario Definition Engine

- Incident types: `pipe_rupture`, `tank_leak`, `vessel_rupture`, `relief_discharge`
- Scenario classifications: `realistic_case`, `worst_case`
- Worst-case defaults include a 10-minute release, ground-level release, `1.5 m/s` wind, and `F` stability screening assumptions
- Inputs supported: inventory, equipment, failure mode, meteorology, release height, topography, conservative mode

### Source Model Service

- Gas and vapor release:
  choked flow, non-choked compressible flow, explicit hole release, pipe release with friction, relief discharge, vessel blowdown inventory limiting
- Liquid release:
  tank-hole gravity discharge, pipe flow, pressure-driven release, friction-limited liquid pipe screening
- Flashing and two-phase:
  flash fraction, vapor mass, entrained liquid estimate, rainout estimation
- Pool formation:
  free-spreading or diked pool area, spreading factor support
- Evaporation:
  heat-transfer-limited, mass-transfer-limited, and boil-off style screening models

### Dispersion Modeling Service

- `gaussian_plume`
- `gaussian_puff`
- `dense_gas`

Derived outputs include plume width, maximum concentration location, and threshold-distance screening where applicable.

### Fire And Explosion Modeling Service

- Fire:
  `jet_fire`, `pool_fire`, `fireball_bleve`
- Explosion:
  `tnt_equivalency`, `multi_energy`, `vce`, `deflagration_screening`, `detonation_screening`
- Blast and mitigation:
  `blast_damage_screening`, `mitigation_screening`
- VCE complexity inputs:
  cloud mass, ignition delay, and congestion factor

### Effect Modeling Service

- `toxic_probit`
- `toxic_dose_response`
- `thermal_probit`
- `thermal_dose_response`
- `explosion_probit`
- `explosion_dose_response`

Population-based summaries are supported through `population_distribution` or `population_count` inputs so client applications can estimate expected burn cases or expected fatalities by exposure zone.

### Toxic Criteria Service

- `toxic_criteria_lookup`
- starter registry covers AEGL, ERPG, IDLH, TLV, PEL, and toxic endpoint lookup for selected chemicals
- request-level criteria overrides are supported for organization-specific datasets

### Prevention And Response Service

- `fire_triangle_screening`
- `autoignition_screening`
- `inerting_requirement`
- `ignition_energy_screening`
- `spray_mist_screening`
- `release_prevention_screening`
- `emergency_response_planning`

### Sign Intelligence

- `sign_analysis`
- accepts sign OCR text or manually entered sign text plus optional sign image payload
- classifies common gas, pipeline, flammable-gas, high-pressure-gas, and toxic-gas signage
- returns a scenario-definition seed, impact-zone seed, recommended services, and required next parameters

### Visualization Layer

- `plume_map`
- `heatmap`
- `risk_contours`
- `time_evolution`

## Implemented Models

### Dispersion

`dispersion.gaussian_puff_ground`

- Purpose: instantaneous ground-level Gaussian puff concentration at a receptor
- Inputs: `x`, `y`, `z`, `Q`, `u`, `sigma_y`, `sigma_z`
- Outputs: `concentration`
- Constants: `shared.pi`

`dispersion.pasquill_gifford_sigma_y`

- Purpose: screening atmospheric dispersion coefficients from distance and stability class
- Inputs: `x`, `stability_class`
- Outputs: `sigma_y`, `sigma_z_screening`
- Constants: none

`dispersion.gaussian_puff_screening_radius`

- Purpose: screening leak impact radius based on a concentration threshold
- Inputs: `released_mass_kg`, `concentration_threshold_kg_m3`, `stability_class`, optional `y`, optional `z`
- Outputs: `impact_radius_m`, `impact_area_m2`, `screening_release_mass_kg`
- Constants: `shared.pi`
- Notes: this is a screening circle, not a full time-varying plume footprint

### Fire And Explosion

`fire.flammability_limits`

- Purpose: temperature-adjusted lower and upper flammability limits
- Inputs: `temp_c`, `lfl_20c`, `ufl_20c`
- Outputs: `lower_flammability_limit`, `upper_flammability_limit`
- Constants: `shared.absolute_zero_offset_c`, `shared.reference_temperature_c`

`fire.point_source_heat_flux`

- Purpose: point-source radiant heat flux at a receptor
- Inputs: `distance_m`, `burning_rate_kg_s`, `heat_of_combustion_kj_kg`
- Outputs: `heat_flux_kw_m2`
- Constants: `shared.pi`, `fire.default_radiative_fraction`, `fire.default_atmospheric_transmissivity`

`fire.point_source_heat_flux_radius`

- Purpose: circular fire impact zone for a selected heat-flux threshold
- Inputs: `burning_rate_kg_s`, `heat_of_combustion_kj_kg`, `impact_threshold_kw_m2`
- Outputs: `impact_radius_m`, `impact_area_m2`
- Constants: `shared.pi`, `fire.default_radiative_fraction`, `fire.default_atmospheric_transmissivity`

## Planned Models

The registry already includes placeholders so downstream applications can integrate once and grow with the library:

- `source.terms.release_rate`
- `toxics.probit.exposure_response`
- `explosion.tnt_equivalency`

## Example Equations

- `C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))`
- `sigma_y = a * x^(1 + b)`
- `sigma_z = a * x / ((1 + b * x)^n)`
- solve for `x` where `C(x) = concentration_threshold`
- `LFL_T = LFL_ref * (T_ref + T_abs) / (T + T_abs)`
- `UFL_T = UFL_ref * (T + T_abs) / (T_ref + T_abs)`
- `q = tau_a * chi_r * m_dot * DeltaH_c / (4 * pi * r^2)`
- `r = sqrt((tau_a * chi_r * m_dot * DeltaH_c) / (4 * pi * q_threshold))`

## Constants

Default constants include:

- `shared.pi`
- `shared.gravity_standard`
- `shared.universal_gas_constant`
- `shared.absolute_zero_offset_c`
- `shared.reference_temperature_c`
- `fire.default_radiative_fraction`
- `fire.default_atmospheric_transmissivity`

### Constant Details

`shared.pi`

- Value: `3.141592653589793`
- Unit: `dimensionless`
- Physical meaning: geometric ratio between circumference and diameter
- Use: Gaussian plume/puff normalization, circular pool area, circular impact areas, and point-source radiation geometry

`shared.gravity_standard`

- Value: `9.80665`
- Unit: `m/s^2`
- Physical meaning: standard terrestrial gravitational acceleration
- Use: gravity-driven tank discharge, liquid outflow velocity, and hydrostatic source-term relations

`shared.universal_gas_constant`

- Value: `8.314462618`
- Unit: `J/mol/K`
- Physical meaning: proportionality constant linking pressure, molar volume, and absolute temperature for gases
- Use: conversion from molecular weight to specific gas constant, compressible gas discharge, and ideal-gas screening conversions

`shared.absolute_zero_offset_c`

- Value: `273.15`
- Unit: `degC`
- Physical meaning: Celsius-to-Kelvin offset
- Use: temperature-dependent flammability and other absolute-temperature conversions

`shared.reference_temperature_c`

- Value: `20.0`
- Unit: `degC`
- Physical meaning: baseline reference state used by the screening flammability-limit relation
- Use: reference temperature for flammability limits

`fire.default_radiative_fraction`

- Value: `0.35`
- Unit: `fraction`
- Physical meaning: fraction of total combustion energy assumed to leave the flame as thermal radiation
- Use: jet fire, pool fire, and fireball radiant heat-flux screening

`fire.default_atmospheric_transmissivity`

- Value: `1.0`
- Unit: `fraction`
- Physical meaning: fraction of thermal radiation assumed to pass through the atmosphere to the receptor
- Use: screening transmissivity multiplier in fire heat-flux and impact-radius calculations

Each request can override model-specific constants without changing the endpoint shape.

## Browser App and GitHub Pages

The static client lives in [`docs/`](docs). It is designed for GitHub Pages and provides:

- OpenStreetMap as the default basemap
- optional uploaded image overlays
- a map for dropping one source pin and multiple receptor pins
- scenario selection for leak and fire screening
- leak and fire asset configuration from a GUI
- impact-circle rendering from `/gis/impact-zones`
- a configurable API base URL stored in browser local storage
- equation and constant panels sourced from the Deep Safety API contract
- a browser-local runtime (`browser://local`) so the core API surface can run without an external backend
- sign-photo workflow support through `/signs/analyze` once OCR or manual sign text is supplied

Deep Safety now supports two static-site runtime patterns:

- GitHub Pages with the browser-local runtime for client-side calculations
- GitHub Pages calling a separately deployed Python API when you want a shared backend

The workflow at [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml) publishes the `docs/` folder.

The Pages site is split into separate pages:

- `index.html` for the product landing page
- `app.html` for the interactive map workflow
- `api-docs.html` for API-first documentation
- `readme.html` for a web version of the repository README

## Jupyter Notebook

An interactive notebook is included at [`notebooks/deepsafety_explorer.ipynb`](notebooks/deepsafety_explorer.ipynb).

It walks through:

- listing registered models
- inspecting equations and constants
- running library-level calculations
- generating fire and leak impact zones
- calling the HTTP API locally with `TestClient`

For direct notebook use as a library:

```python
from deepsafety import DeepSafetyClient

client = DeepSafetyClient("http://127.0.0.1:8000")
client.get_service_catalog()
```
## Installation

Install the package:

```powershell
pip install deepsafety
```

For notebook workflows:

```powershell
pip install "deepsafety[jupyter]"
```

## Running the API

```powershell
& 'E:\conda-env\krionis-tester-2\python.exe' -m uvicorn deepsafety.api:app --host 127.0.0.1 --port 8000
```

After installation, you can also use:

```powershell
deepsafety-api
```

or:

```powershell
python -m deepsafety
```

## Docker

Build and run the API container:

```powershell
docker build -t deepsafety .
docker run --rm -p 8000:8000 deepsafety
```

Or with Compose:

```powershell
docker compose up --build
```

The container exposes the same `deepsafety` package and API used for local Python and Jupyter workflows.

## MCP Server

The MCP bridge is implemented in [`deepsafety/mcp_server.py`](deepsafety/mcp_server.py). It exposes tools for:

- listing models
- fetching model metadata
- running calculations
- evaluating map scenarios
- listing constants
- generating impact zones
- analyzing signs into leak-ready scenario seeds

Point it at the API with `DEEPSAFETY_API_BASE`, then launch it with the `deepsafety-mcp` entry point after installation.

