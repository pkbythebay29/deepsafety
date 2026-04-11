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

    def list_models(self, include_planned: bool = True) -> Any:
        return self._request("GET", f"/models?include_planned={str(include_planned).lower()}")

    def get_model(self, model_id: str) -> Any:
        return self._request("GET", f"/models/{model_id}")

    def define_scenario(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/scenario-engine/define", payload)

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

    def solve_dispersion_model(self, model_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/dispersion-models/solve",
            {"model_type": model_type, "inputs": inputs},
        )

    def solve_fire_explosion_model(self, model_type: str, inputs: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/fire-explosion-models/solve",
            {"model_type": model_type, "inputs": inputs},
        )

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
