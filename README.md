# DeepSafety
**DeepSafety** is an open-source process safety consequence-analysis platform. It includes a Python library, a FastAPI service, a GitHub Pages GIS console, an MCP bridge, and a Jupyter notebook so the same calculations can be embedded into web apps, engineering tools, agent workflows, and exploratory engineering analysis.

## Features (Planned and In Progress)

- Atmospheric dispersion models (Pasquill–Gifford)
  - Puff and plume models (ground level and elevated sources)
  - Neutrally buoyant and dense gas behavior
- Toxic effect criteria
  - AEGLs, ERPGs, IDLH, TLVs, PELs, and toxic endpoints
- Flammability and ignition analysis
  - Limits, autoignition, inerting, ignition energy
- Explosion modeling
  - TNT equivalency, VCEs, BLEVEs, deflagration/detonation
  - Blast damage, overpressure, and mitigation
- Fire triangle modeling and spray/mist behavior
- Release prevention and emergency response planning

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
  choked flow, non-choked compressible flow, pipe/hole-style discharge
- Liquid release:
  tank-hole gravity discharge, pressurized liquid release
- Flashing and two-phase:
  flash fraction, vapor mass, rainout mass
- Pool formation:
  free-spreading or diked pool area
- Evaporation:
  heat-transfer-limited and mass-transfer-limited screening models

### Dispersion Modeling Service

- `gaussian_plume`
- `gaussian_puff`
- `dense_gas`

Derived outputs include plume width, maximum concentration location, and threshold-distance screening where applicable.

### Fire And Explosion Modeling Service

- Fire:
  `jet_fire`, `pool_fire`, `fireball_bleve`
- Explosion:
  `tnt_equivalency`, `multi_energy`, `vce`

### Effect Modeling Service

- `toxic_probit`
- `thermal_probit`
- `explosion_probit`

### Visualization Layer

- `plume_map`
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

## GIS and GitHub Pages

The static client lives in [`docs/`](docs). It is designed for GitHub Pages and provides:

- OpenStreetMap as the default basemap
- optional uploaded image overlays
- a map for dropping one source pin and multiple receptor pins
- scenario selection for leak and fire screening
- leak and fire asset configuration from a GUI
- impact-circle rendering from `/gis/impact-zones`
- a configurable API base URL stored in browser local storage
- equation and constant panels sourced from the live API

GitHub Pages can host the static UI and docs, but not the Python API itself. The intended deployment split is:

- GitHub Pages for the static GIS console
- a separate Python host for the FastAPI backend

The workflow at [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml) publishes the `docs/` folder.

## Jupyter Notebook

An interactive notebook is included at [`notebooks/deepsafety_explorer.ipynb`](notebooks/deepsafety_explorer.ipynb).

It walks through:

- listing registered models
- inspecting equations and constants
- running library-level calculations
- generating fire and leak impact zones
- calling the HTTP API locally with `TestClient`

## Running the API

```powershell
& 'E:\conda-env\krionis-tester-2\python.exe' -m uvicorn deepsafety.api:app --host 127.0.0.1 --port 8000
```

## MCP Server

The MCP bridge is implemented in [`deepsafety/mcp_server.py`](deepsafety/mcp_server.py). It exposes tools for:

- listing models
- fetching model metadata
- running calculations
- evaluating GIS scenarios
- listing constants

Point it at the API with `DEEPSAFETY_API_BASE`, then launch it with the `deepsafety-mcp` entry point after installation.
