from __future__ import annotations

from typing import Any

import httpx


class DeepSafetyClient:
    """
    Lightweight Python client for the DeepSafety API.

    This is intended for notebooks, scripts, and application integrations that
    want typed endpoint wrappers without interacting with raw URLs manually.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(method, f"{self.base_url}{path}", json=json_body)
            response.raise_for_status()
            return response.json()

    def request(self, method: str, path: str, json_body: dict[str, Any] | None = None) -> Any:
        return self._request(method, path, json_body)

    def list_models(self, include_planned: bool = True) -> Any:
        return self._request("GET", f"/models?include_planned={str(include_planned).lower()}")

    def get_model(self, model_id: str) -> Any:
        return self._request("GET", f"/models/{model_id}")

    def list_scenarios(
        self,
        page_size: int = 50,
        page_token: str | None = None,
        status: str | None = None,
        query: str | None = None,
    ) -> Any:
        params = [f"page_size={page_size}"]
        if page_token:
            params.append(f"page_token={page_token}")
        if status:
            params.append(f"status={status}")
        if query:
            params.append(f"q={query}")
        return self._request("GET", f"/scenarios?{'&'.join(params)}")

    def create_scenario(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/scenarios", payload)

    def get_scenario(self, scenario_id: str) -> Any:
        return self._request("GET", f"/scenarios/{scenario_id}")

    def validate_scenario(self, scenario_id: str) -> Any:
        return self._request("POST", f"/scenarios/{scenario_id}/validate")

    def list_analyses(self, scenario_id: str | None = None, page_size: int = 50, page_token: str | None = None) -> Any:
        params = [f"page_size={page_size}"]
        if scenario_id:
            params.append(f"scenario_id={scenario_id}")
        if page_token:
            params.append(f"page_token={page_token}")
        return self._request("GET", f"/analyses?{'&'.join(params)}")

    def create_analysis(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/analyses", payload)

    def get_analysis(self, analysis_id: str) -> Any:
        return self._request("GET", f"/analyses/{analysis_id}")

    def create_simulation(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/simulations", payload)

    def get_simulation(self, simulation_id: str) -> Any:
        return self._request("GET", f"/simulations/{simulation_id}")

    def get_job(self, job_id: str) -> Any:
        return self._request("GET", f"/jobs/{job_id}")

    def create_report(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/reports", payload)

    def define_scenario(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/scenario-engine/define", payload)

    def get_scenario_catalog(self) -> Any:
        return self._request("GET", "/scenario-catalog")

    def list_materials(self, query: str | None = None, page: int = 1, page_size: int = 20) -> Any:
        suffix = f"?page={page}&pageSize={page_size}"
        if query:
            suffix = f"?q={query}&page={page}&pageSize={page_size}"
        return self._request("GET", f"/materials{suffix}")

    def get_material(self, material_id: str) -> Any:
        return self._request("GET", f"/materials/{material_id}")

    def get_material_toxicity(self, material_id: str) -> Any:
        return self._request("GET", f"/materials/{material_id}/toxicity")

    def convert_concentration(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/health/convert-concentration", payload)

    def evaluate_probit(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/health/probit/evaluate", payload)

    def list_scenario_templates(self) -> Any:
        return self._request("GET", "/scenario-library/templates")

    def get_service_catalog(self) -> Any:
        return self._request("GET", "/service-catalog")

    def solve_source_model(self, model_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/source-models/solve",
            {"model_type": model_type, "inputs": inputs},
        )

    def select_release_scenario(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/source-models/scenario/select", payload)

    def apply_conservative_source_analysis(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/source-models/conservative-analysis", payload)

    def solve_dispersion_model(self, model_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/dispersion-models/solve",
            {"model_type": model_type, "inputs": inputs},
        )

    def run_gaussian_plume(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/dispersion/gaussian-plume", payload)

    def run_gaussian_puff(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/dispersion/gaussian-puff", payload)

    def run_dense_gas(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/dispersion/dense-gas", payload)

    def solve_fire_explosion_model(self, model_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/fire-explosion-models/solve",
            {"model_type": model_type, "inputs": inputs},
        )

    def evaluate_vce(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/fire-explosion/vce", payload)

    def evaluate_bleve(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/fire-explosion/bleve", payload)

    def solve_effect_model(self, model_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/effect-models/solve",
            {"model_type": model_type, "inputs": inputs},
        )

    def solve_visualization(self, layer_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/visualization/solve",
            {"layer_type": layer_type, "inputs": inputs},
        )

    def get_impact_zones(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/gis/impact-zones", payload)

    def list_pipeline_routes(self) -> Any:
        return self._request("GET", "/gis/pipeline-routes")

    def create_pipeline_route(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/gis/pipeline-routes", payload)

    def get_pipeline_route(self, route_id: str) -> Any:
        return self._request("GET", f"/gis/pipeline-routes/{route_id}")

    def evaluate_pipeline_route(self, route_id: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", f"/gis/pipeline-routes/{route_id}/evaluate", payload)

    def get_pipeline_route_impact_zones(self, route_id: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", f"/gis/pipeline-routes/{route_id}/impact-zones", payload)
