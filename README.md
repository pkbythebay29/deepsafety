# DeepSafety
**DeepSafety** is an open-source process safety consequence-analysis platform. It includes a Python library, a FastAPI service, a GitHub Pages GIS console, and an MCP bridge so the same calculations can be embedded into web apps, engineering tools, and agent workflows.

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
- `POST /gis/scenarios/evaluate` for source-pin and receptor-pin workflows

Each model documents the equations used and the constants applied in the response itself.

## Implemented Models

- `dispersion.gaussian_puff_ground`
- `dispersion.pasquill_gifford_sigma_y`
- `fire.flammability_limits`
- `fire.point_source_heat_flux`

Planned models are also registered so downstream applications can integrate once and adopt more consequence modules over time.

## Example Equations

- `C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))`
- `sigma_y = a * x^(1 + b)`
- `sigma_z = a * x / ((1 + b * x)^n)`
- `LFL_T = LFL_ref * (T_ref + T_abs) / (T + T_abs)`
- `UFL_T = UFL_ref * (T + T_abs) / (T_ref + T_abs)`
- `q = tau_a * chi_r * m_dot * DeltaH_c / (4 * pi * r^2)`

## Constants

Default constants include:

- `shared.pi`
- `shared.absolute_zero_offset_c`
- `shared.reference_temperature_c`
- `fire.default_radiative_fraction`
- `fire.default_atmospheric_transmissivity`

Each request can override model-specific constants without changing the endpoint shape.

## GIS and GitHub Pages

The static client lives in [`docs/`](docs). It is designed for GitHub Pages and provides:

- a map for dropping one source pin and multiple receptor pins
- scenario selection for leak and fire screening
- a configurable API base URL stored in browser local storage
- equation and constant panels sourced from the live API

GitHub Pages can host the static UI and docs, but not the Python API itself. The intended deployment split is:

- GitHub Pages for the static GIS console
- a separate Python host for the FastAPI backend

The workflow at [`.github/workflows/deploy-pages.yml`](.github/workflows/deploy-pages.yml) publishes the `docs/` folder.

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
