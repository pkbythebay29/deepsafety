# Release Notes

## 1.0.2

This release adds persisted pipeline-route workflows across the API, browser app, and Python client, then aligns the docs and package metadata for publication.

### Added

- Persisted GIS pipeline routes with GPS coordinates:
  - `GET /gis/pipeline-routes`
  - `POST /gis/pipeline-routes`
  - `GET /gis/pipeline-routes/{route_id}`
- Route-aware consequence analysis:
  - `POST /gis/pipeline-routes/{route_id}/evaluate`
  - `POST /gis/pipeline-routes/{route_id}/impact-zones`
- Python client helpers for pipeline-route creation, retrieval, receptor analysis, and impact-zone analysis
- Interactive app support for drawing a pipeline polyline and running leak analysis against the snapped release location

### Changed

- GIS responses now include the snapped release point and pipeline route geometry when route-based analysis is used
- Browser-local website runtime now mirrors the pipeline-route API contract so the app works without an external backend
- Website docs and release metadata now reflect the route-aware GIS workflow and new package version

## 1.0.1

This release reconciles the published package with the latest repository state and activates automated PyPI release publishing through GitHub Actions.

### Added

- GitHub Actions workflow for PyPI publishing on `v*` tags and manual dispatch (`publish-pypi.yml`)
- CI artifact validation with `python -m build` and `twine check`
- New tutorial notebooks:
  - `notebooks/buncefield_tutorial.ipynb`
  - `notebooks/csb_incident_tutorial.ipynb`

### Changed

- Documentation and landing pages now position Deep Safety as a foundational, physics-driven integration layer
- API reference expanded with POST endpoint contract tables and JSON templates
- App impact display now uses consequence rings (severe, primary, awareness)
- Removed remaining references to Crowl/Louvar naming in API metadata

## 1.0.0

Deep Safety 1.0.0 aligns the Python package and FastAPI service around the expanded OpenAPI contract and the physical modeling chain used by the project.

### Added

- OpenAPI-aligned endpoint families for:
  - materials and material subprofiles
  - health and industrial hygiene
  - split source-model routes and conservative scenario selection
  - split dispersion routes and result-driven isopleths
  - fire and explosion utility routes
  - prevention, reactivity, relief, and hazard-evaluation workflows
- Python client helpers for materials, health, scenario selection, and dispersion/fire workflows
- Generic MCP `call_api_path` tool so agents can reach newly added API routes immediately
- Direct API tests for the expanded OpenAPI surface

### Changed

- Package metadata, description, and documentation now match the API surface and modeling chain
- Starter material data is now loaded from packaged JSON registry files instead of being embedded in Python code
- Starter toxic criteria is now loaded from packaged JSON registry files instead of being embedded in Python code
- Shared constants are now loaded from a packaged constants registry with explicit physical meaning and provenance

### Notes

- The packaged material and toxic datasets are starter registries intended for integration and extension, not a substitute for organization-approved property packages or toxicology libraries.
- Browser-local runtime remains focused on the core interactive workflow while the full OpenAPI-aligned surface is available through the FastAPI service and Python client.
