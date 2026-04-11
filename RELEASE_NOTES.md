# Release Notes

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
