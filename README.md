# DeepSafety
**DeepSafety** is an open-source process safety consequence-analysis platform. It includes a Python library, a FastAPI service, a browser-local runtime for GitHub Pages, an MCP bridge, and a Jupyter notebook so the same calculations can be embedded into web apps, engineering tools, agent workflows, and exploratory engineering analysis.

## Implemented API Capabilities

- Atmospheric dispersion models (Pasquill-Gifford)
  - Puff and plume models
  - ground-level and elevated-source screening
  - dense-gas screening and neutrally buoyant screening relations
- Toxic effect criteria
  - starter toxic criteria registry for AEGL, ERPG, IDLH, TLV, PEL, and toxic endpoints
  - toxic probit and toxic dose-response services
- Flammability and ignition analysis
  - flammability limits
  - autoignition screening
  - inerting requirement screening
  - ignition energy screening
- Explosion modeling
  - TNT equivalency
  - VCE
  - BLEVE fireball
  - deflagration screening
  - detonation screening
  - blast damage screening
  - mitigation screening
- Fire triangle modeling and spray/mist behavior
  - fire triangle screening
  - spray/mist fire screening
- Release prevention and emergency response planning
  - release prevention screening
  - emergency response planning screening

## License
This project is licensed under the MIT License. 

## Contributing

Contributions are welcome. Please fork the repository, open a pull request, and include tests for any new functionality.

## API Surface

The HTTP service now exposes:

- `GET /models` for discovery
- `GET /models/{model_id}` for equations, constants, and I/O definitions
- `POST /models/{model_id}/calculate` for direct model execution
- `GET /constants` and `GET /constants/{model_id}` for the modifiable default constants registry
- `GET /scenarios` for scenario-driven discovery
- `POST /scenario-engine/define` for incident builder + classification normalization
- `GET /scenario-library/templates` for prebuilt scenario templates
- `POST /source-models/solve` for source-term screening models
- `POST /dispersion-models/solve` for plume, puff, and dense-gas screening
- `POST /fire-explosion-models/solve` for fire and explosion screening models
- `POST /effect-models/solve` for toxic, thermal, and explosion effects
- `POST /toxic-criteria/lookup` for starter AEGL, ERPG, IDLH, TLV, PEL, and toxic-endpoint lookup
- `POST /prevention-response-models/solve` for ignition, inerting, spray/mist, prevention, and emergency-response screening
- `POST /signs/analyze` for sign intelligence that turns OCR or manually entered sign text into a leak-ready scenario seed
- `POST /visualization/solve` for plume maps, contours, and time-evolution payloads
- `POST /gis/scenarios/evaluate` for source-pin and receptor-pin workflows
- `POST /gis/impact-zones` for map-ready impact circles

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
- `shared.absolute_zero_offset_c`
- `shared.reference_temperature_c`
- `fire.default_radiative_fraction`
- `fire.default_atmospheric_transmissivity`

### Constant Details

`shared.pi`

- Value: `3.141592653589793`
- Unit: `dimensionless`
- Use: Gaussian and radiation equations

`shared.absolute_zero_offset_c`

- Value: `273.15`
- Unit: `degC`
- Use: Celsius-to-Kelvin offset in flammability calculations

`shared.reference_temperature_c`

- Value: `20.0`
- Unit: `degC`
- Use: reference temperature for flammability limits

`fire.default_radiative_fraction`

- Value: `0.35`
- Unit: `fraction`
- Use: default radiant fraction in fire heat-flux models

`fire.default_atmospheric_transmissivity`

- Value: `1.0`
- Unit: `fraction`
- Use: screening transmissivity multiplier in fire heat-flux models

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

