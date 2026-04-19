# Deep Safety

Deep Safety is a physics-based process safety platform for **verifiable consequence analysis, hazard evaluation, and software integration**.

Documentation site: [deepsafety.tech](https://deepsafety.tech)

It gives teams one model contract that can be used across:
- Python notebooks
- FastAPI services
- GitHub Pages browser-local workflows
- MCP and agent tooling
- Docker deployments

Deep Safety keeps the physics explicit and reusable so decision systems can rely on a consistent chain for source terms, dispersion, fire and explosion metrics, effects, and hazard-study workflows.

## Quick Start

```text
user@deepsafety.tech:~$ pip install deepsafety
Collecting deepsafety ...
Successfully installed deepsafety
user@deepsafety.tech:~$ deepsafety-api --host 0.0.0.0 --port 8000
Deep Safety API ready at http://0.0.0.0:8000  _
```

```bash
# Optional notebook stack
$ pip install "deepsafety[jupyter]"
```

## Why Deep Safety

- Physics-first model chain: materials -> source -> dispersion/effects -> hazard evaluation
- Verifiable formulas: equations are documented and exposed in API metadata
- Transparent constants: physical meaning and source are documented
- Cross-platform integration: same model vocabulary in API, notebooks, app, and MCP tools
- Sensitivity-friendly design: constants can be overridden per request
- Product-ready deployment: package, Docker image, static site, and API are designed to be consumed directly by applications

## Model Chain

1. Materials and operating conditions define the basis.
2. Scenario and source models calculate release rate, duration, and phase state.
3. Dispersion, fire and explosion, and effect models compute consequence metrics.
4. Hazard-evaluation workflows consume the same outputs in HAZOP, FMEA, and What-If studies.

## Data Provenance

Starter registries are packaged as JSON data (not hard-coded in model logic):

- `deepsafety/data/materials_registry.json`
- `deepsafety/data/toxic_criteria_registry.json`
- `deepsafety/data/constants_registry.json`

This keeps assumptions inspectable, versionable, and easier to govern.

## Constants Override Example

Constants can be overridden request-by-request for sensitivity studies and controlled assumption audits.

```json
{
  "model_type": "jet_fire",
  "inputs": {
    "release_rate_kg_s": 2.5,
    "heat_of_combustion_kj_kg": 46000,
    "distance_m": 35
  },
  "constants": {
    "fire.default_radiative_fraction": 0.4
  }
}
```

```python
from deepsafety import DeepSafetyClient

client = DeepSafetyClient("http://127.0.0.1:8000")
result = client.calculate(
    "fire.point_source_heat_flux",
    {
        "distance_m": 35,
        "burning_rate_kg_s": 2.5,
        "heat_of_combustion_kj_kg": 46000,
    },
    constants={"fire.default_radiative_fraction": 0.4},
)
```

## API Surface

Core service and metadata:
- `GET /models`
- `GET /models/{model_id}`
- `POST /models/{model_id}/calculate`
- `GET /constants`
- `GET /constants/{model_id}`
- `GET /service-catalog`

Materials and health:
- `GET /materials`
- `GET /materials/{materialId}`
- `GET /materials/{materialId}/toxicity`
- `GET /materials/{materialId}/flammability`
- `GET /materials/{materialId}/reactivity`
- `POST /health/convert-concentration`
- `POST /health/probit/evaluate`
- `POST /health/exposure/twa`
- `POST /health/exposure/compliance`
- `POST /industrial-hygiene/ventilation/dilution`
- `POST /industrial-hygiene/ventilation/local-exhaust`
- `POST /industrial-hygiene/liquid-pool/evaporation`

Scenario and source:
- `POST /scenario-engine/define`
- `GET /scenario-library/templates`
- `POST /source-models/liquid-hole`
- `POST /source-models/tank-hole`
- `POST /source-models/liquid-pipe`
- `POST /source-models/gas-hole`
- `POST /source-models/gas-pipe`
- `POST /source-models/flashing-liquid`
- `POST /source-models/scenario/select`
- `POST /source-models/conservative-analysis`
- `POST /source-models/solve`

Dispersion, fire/explosion, effects:
- `POST /dispersion/gaussian-plume`
- `POST /dispersion/gaussian-puff`
- `POST /dispersion/dense-gas`
- `POST /dispersion/isopleth`
- `POST /dispersion/toxic-endpoints/evaluate`
- `POST /dispersion/prevention-mitigation`
- `POST /dispersion-models/solve`
- `POST /fire-explosion/flammability/mixture`
- `POST /fire-explosion/loc`
- `POST /fire-explosion/ignition-energy`
- `POST /fire-explosion/tnt-equivalency`
- `POST /fire-explosion/multi-energy`
- `POST /fire-explosion/vce`
- `POST /fire-explosion/bleve`
- `POST /fire-explosion-models/solve`
- `POST /effect-models/solve`
- `POST /toxic-criteria/lookup`

Prevention, reactivity, relief, hazard evaluation:
- `POST /prevention/inerting/purge`
- `POST /prevention/static-electricity/risk`
- `POST /prevention/area-classification`
- `POST /prevention/fire-protection/strategy`
- `POST /reactivity/calorimetry/interpret`
- `POST /reactivity/screening`
- `POST /reactivity/control`
- `POST /relief/devices/select`
- `POST /relief/system/analyze`
- `POST /relief/effluent-handling/select`
- `POST /relief/sizing/liquid`
- `POST /relief/sizing/gas-vapor`
- `POST /relief/sizing/two-phase`
- `POST /relief/sizing/deflagration-vent`
- `POST /relief/sizing/external-fire`
- `POST /relief/sizing/thermal-expansion`
- `POST /hazard-evaluation/checklist`
- `POST /hazard-evaluation/safety-review`
- `POST /hazard-evaluation/inherent-safety-review`
- `POST /hazard-evaluation/preliminary-hazard-analysis`
- `POST /hazard-evaluation/relative-ranking`
- `POST /hazard-evaluation/hazop`
- `POST /hazard-evaluation/fmea`
- `POST /hazard-evaluation/what-if`
- `POST /hazard-evaluation/what-if-checklist`
- `POST /hazard-evaluation/information-requirements/validate`
- `POST /prevention-response-models/solve`

GIS, visualization, and sign analysis:
- `POST /visualization/solve`
- `POST /signs/analyze`
- `GET /gis/pipeline-routes`
- `POST /gis/pipeline-routes`
- `GET /gis/pipeline-routes/{route_id}`
- `POST /gis/scenarios/evaluate`
- `POST /gis/impact-zones`
- `POST /gis/pipeline-routes/{route_id}/evaluate`
- `POST /gis/pipeline-routes/{route_id}/impact-zones`

## GitHub Pages Structure

- `docs/index.html` -> documentation landing page
- `docs/api-docs.html` -> endpoint and formula reference
- `docs/tutorials.html` -> guided training and incident walkthroughs
- `docs/use-cases.html` -> interactive/app + notebook entry points
- `docs/app.html` -> interactive map app (with consequence rings)
- `docs/readme.html` -> web copy of this README

The public documentation surface is published at [deepsafety.tech](https://deepsafety.tech).

## Notebook Entry Points

- `notebooks/all_endpoints_tutorial_workbook.ipynb`
- `notebooks/deepsafety_explorer.ipynb`
- `notebooks/buncefield_tutorial.ipynb`
- `notebooks/csb_incident_tutorial.ipynb`

## Runtime Options

```bash
# Local API
python -m uvicorn deepsafety.api:app --host 127.0.0.1 --port 8000

# Docker
docker build -t deepsafety .
docker run --rm -p 8000:8000 deepsafety

# Compose
docker compose up --build
```

## CI/CD and PyPI Publishing

Deep Safety publishes through GitHub Actions:

- `CI` workflow:
  - runs tests
  - builds `sdist` and `wheel`
  - runs `twine check` on artifacts
- `Publish PyPI` workflow (`.github/workflows/publish-pypi.yml`):
  - triggers on tags matching `v*` and on manual dispatch
  - reruns tests and package checks before publish
  - publishes artifacts to PyPI

Required repository configuration:

- Add `PYPI_API_TOKEN` in GitHub secrets (repository or `pypi` environment secret)
- Optional fallback secret name: `PYPI_TOKEN`
- Optional org/repo-specific fallback: `DEEPSAFETYPYPI`
- Configure a `pypi` environment in GitHub if you want protected release approvals

Release flow:

```bash
git tag v1.0.2
git push origin v1.0.2
```

## MCP

`deepsafety-mcp` exposes Deep Safety operations for tool-driven and agent-driven workflows against the same API model chain.

## License

MIT
