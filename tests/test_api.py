import pytest
from fastapi.testclient import TestClient

from deepsafety.api import create_app


client = TestClient(create_app())


def test_health_endpoint() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_models_endpoint_lists_implemented_and_planned_models() -> None:
    response = client.get("/models")

    assert response.status_code == 200
    payload = response.json()

    assert any(model["id"] == "dispersion.gaussian_puff_ground" for model in payload)
    assert any(model["status"] == "planned" for model in payload)


def test_model_detail_exposes_required_metadata() -> None:
    response = client.get("/models/fire.flammability_limits")

    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == "fire.flammability_limits"
    assert payload["status"] == "implemented"
    assert payload["equations"]
    assert payload["constants"]
    assert payload["input_fields"]
    assert payload["output_fields"]


def test_calculate_flammability_limits() -> None:
    response = client.post(
        "/models/fire.flammability_limits/calculate",
        json={"inputs": {"temp_c": 50, "lfl_20c": 2.1, "ufl_20c": 9.5}},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["model"]["id"] == "fire.flammability_limits"
    assert payload["outputs"]["lower_flammability_limit"] == 1.905
    assert payload["outputs"]["upper_flammability_limit"] == 10.472


def test_planned_models_return_not_implemented() -> None:
    response = client.post(
        "/models/explosion.tnt_equivalency/calculate",
        json={"inputs": {"mass": 20}},
    )

    assert response.status_code == 501


def test_invalid_inputs_return_bad_request() -> None:
    response = client.post(
        "/models/dispersion.pasquill_gifford_sigma_y/calculate",
        json={"inputs": {"x": -10, "stability_class": "D"}},
    )

    assert response.status_code == 400
    assert "greater than zero" in response.json()["detail"]


def test_constants_endpoint_lists_defaults() -> None:
    response = client.get("/constants/fire.point_source_heat_flux")

    assert response.status_code == 200
    payload = response.json()

    assert any(item["name"] == "fire.default_radiative_fraction" for item in payload)


def test_calculate_point_source_heat_flux_with_constant_override() -> None:
    response = client.post(
        "/models/fire.point_source_heat_flux/calculate",
        json={
            "inputs": {
                "distance_m": 25,
                "burning_rate_kg_s": 4.5,
                "heat_of_combustion_kj_kg": 46000,
            },
            "constants": {"fire.default_radiative_fraction": 0.4},
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["outputs"]["heat_flux_kw_m2"] == pytest.approx(10.542423, rel=1e-6)
    assert any(
        item["name"] == "fire.default_radiative_fraction" and item["source"] == "override"
        for item in payload["constants"]
    )


def test_gis_fire_scenario_returns_receptor_results() -> None:
    response = client.post(
        "/gis/scenarios/evaluate",
        json={
            "scenario_type": "fire",
            "source": {
                "latitude": 51.5074,
                "longitude": -0.1278,
                "label": "Tank",
            },
            "receptors": [
                {
                    "id": "control-room",
                    "label": "Control Room",
                    "latitude": 51.5079,
                    "longitude": -0.1268,
                }
            ],
            "inputs": {
                "burning_rate_kg_s": 4.5,
                "heat_of_combustion_kj_kg": 46000,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["scenario_type"] == "fire"
    assert payload["model"]["id"] == "fire.point_source_heat_flux"
    assert len(payload["receptors"]) == 1
    assert payload["receptors"][0]["distance_m"] > 0
    assert "heat_flux_kw_m2" in payload["receptors"][0]["outputs"]
    assert payload["geojson"]["type"] == "FeatureCollection"


def test_gis_leak_scenario_autofills_sigma_values_from_stability_class() -> None:
    response = client.post(
        "/gis/scenarios/evaluate",
        json={
            "scenario_type": "leak",
            "source": {
                "latitude": 51.5074,
                "longitude": -0.1278,
            },
            "receptors": [
                {
                    "id": "gate",
                    "latitude": 51.5076,
                    "longitude": -0.1272,
                }
            ],
            "inputs": {
                "Q": 25,
                "u": 3.5,
                "stability_class": "D",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["model"]["id"] == "dispersion.gaussian_puff_ground"
    assert payload["receptors"][0]["outputs"]["concentration"] > 0


def test_fire_impact_zones_return_circle_geometry() -> None:
    response = client.post(
        "/gis/impact-zones",
        json={
            "scenario_type": "fire",
            "source": {
                "latitude": 51.5074,
                "longitude": -0.1278,
                "label": "Pump Area",
            },
            "asset": {
                "burning_rate_kg_s": 4.5,
                "heat_of_combustion_kj_kg": 46000,
            },
            "criteria": [
                {"label": "Personnel pain threshold", "threshold": 4.0, "unit": "kW/m^2"},
                {"label": "Severe damage threshold", "threshold": 12.5, "unit": "kW/m^2"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["model"]["id"] == "fire.point_source_heat_flux_radius"
    assert len(payload["zones"]) == 2
    assert payload["zones"][0]["radius_m"] > payload["zones"][1]["radius_m"]
    assert any(feature["geometry"]["type"] == "Polygon" for feature in payload["geojson"]["features"])


def test_leak_impact_zones_accept_gas_line_style_asset_inputs() -> None:
    response = client.post(
        "/gis/impact-zones",
        json={
            "scenario_type": "leak",
            "source": {
                "latitude": 51.5074,
                "longitude": -0.1278,
                "label": "Gas Line Segment",
            },
            "asset": {
                "line_pressure_kpa": 6000,
                "mass_flow_kg_s": 1.2,
                "gas_temperature_c": 18,
                "leak_duration_s": 60,
                "stability_class": "D",
            },
            "criteria": [
                {"label": "Concern threshold", "threshold": 0.02, "unit": "kg/m^3"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["model"]["id"] == "dispersion.gaussian_puff_screening_radius"
    assert payload["zones"][0]["radius_m"] >= 0
    assert payload["zones"][0]["outputs"]["screening_release_mass_kg"] == pytest.approx(72.0)
