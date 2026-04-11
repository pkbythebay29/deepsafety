from fastapi.testclient import TestClient

from deepsafety.api import create_app


client = TestClient(create_app())


def test_scenario_definition_applies_worst_case_defaults() -> None:
    response = client.post(
        "/scenario-engine/define",
        json={
            "incident_type": "pipe_rupture",
            "classification": "worst_case",
            "inventory": {"mass_kg": 1000, "phase": "gas"},
            "equipment": {"diameter_m": 0.15},
        },
    )

    assert response.status_code == 200
    payload = response.json()["scenario"]
    assert payload["release_duration_s"] == 600.0
    assert payload["release_height_m"] == 0.0
    assert payload["meteorology"]["wind_speed_m_s"] == 1.5
    assert payload["meteorology"]["stability_class"] == "F"
    assert payload["references"]


def test_scenario_library_lists_templates() -> None:
    response = client.get("/scenario-library/templates")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == "pipeline_leak" for item in payload)
    assert any("recommended_services" in item for item in payload)


def test_service_catalog_exposes_equations_and_references() -> None:
    response = client.get("/service-catalog")

    assert response.status_code == 200
    payload = response.json()
    assert "source_models" in payload
    gas_release = next(item for item in payload["source_models"] if item["model_type"] == "gas_release")
    assert gas_release["equations"]
    assert gas_release["references"]


def test_source_model_gas_release_returns_release_rate_and_mass() -> None:
    response = client.post(
        "/source-models/solve",
        json={
            "model_type": "gas_release",
            "inputs": {
                "diameter_m": 0.02,
                "upstream_pressure_pa": 5_000_000,
                "downstream_pressure_pa": 101_325,
                "temperature_k": 288.15,
                "heat_capacity_ratio": 1.3,
                "molecular_weight_kg_kmol": 16.04,
                "duration_s": 60,
                "discharge_geometry": "pipe",
                "conservative_mode": True,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["outputs"]["release_rate_kg_s"] > 0
    assert payload["outputs"]["total_mass_kg"] > payload["outputs"]["release_rate_kg_s"]
    assert payload["equations"]
    assert payload["constants"]
    assert payload["references"]


def test_dispersion_service_gaussian_plume_returns_threshold_distance() -> None:
    response = client.post(
        "/dispersion-models/solve",
        json={
            "model_type": "gaussian_plume",
            "inputs": {
                "release_rate_kg_s": 2.0,
                "wind_speed_m_s": 3.0,
                "x_m": 200,
                "stability_class": "D",
                "threshold_kg_m3": 1e-5,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["concentration_kg_m3"] > 0
    assert payload["distance_to_threshold_m"] is not None


def test_dense_gas_screening_returns_slumping_metrics() -> None:
    response = client.post(
        "/dispersion-models/solve",
        json={
            "model_type": "dense_gas",
            "inputs": {
                "released_mass_kg": 500,
                "gas_density_kg_m3": 3.0,
                "release_duration_s": 120,
                "wind_speed_m_s": 2.0,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["cloud_radius_m"] > 0
    assert payload["cloud_length_m"] >= payload["cloud_radius_m"]


def test_fire_explosion_service_vce_responds_to_delay_and_congestion() -> None:
    response = client.post(
        "/fire-explosion-models/solve",
        json={
            "model_type": "vce",
            "inputs": {
                "cloud_mass_kg": 800,
                "heat_of_combustion_kj_kg": 46000,
                "ignition_delay_s": 20,
                "congestion_factor": 1.5,
                "distance_m": 120,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["yield_factor"] > 0
    assert payload["overpressure_kpa"] > 0


def test_fire_explosion_service_jet_fire_is_available() -> None:
    response = client.post(
        "/fire-explosion-models/solve",
        json={
            "model_type": "jet_fire",
            "inputs": {
                "release_rate_kg_s": 3.0,
                "heat_of_combustion_kj_kg": 46000,
                "distance_m": 30,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["heat_flux_kw_m2"] > 0
    assert payload["flame_length_m"] > 0


def test_fire_explosion_service_pool_fire_is_available() -> None:
    response = client.post(
        "/fire-explosion-models/solve",
        json={
            "model_type": "pool_fire",
            "inputs": {
                "pool_area_m2": 40,
                "burning_flux_kg_m2_s": 0.05,
                "heat_of_combustion_kj_kg": 44000,
                "distance_m": 35,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["burning_rate_kg_s"] > 0
    assert payload["heat_flux_kw_m2"] > 0


def test_fire_explosion_service_fireball_bleve_is_available() -> None:
    response = client.post(
        "/fire-explosion-models/solve",
        json={
            "model_type": "fireball_bleve",
            "inputs": {
                "fuel_mass_kg": 1200,
                "heat_of_combustion_kj_kg": 46000,
                "distance_m": 80,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["fireball_diameter_m"] > 0
    assert payload["fireball_duration_s"] > 0


def test_fire_explosion_service_tnt_equivalency_is_available() -> None:
    response = client.post(
        "/fire-explosion-models/solve",
        json={
            "model_type": "tnt_equivalency",
            "inputs": {
                "fuel_mass_kg": 300,
                "heat_of_combustion_kj_kg": 46000,
                "explosion_efficiency": 0.1,
                "distance_m": 100,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["tnt_equivalent_mass_kg"] > 0
    assert payload["overpressure_kpa"] > 0


def test_fire_explosion_service_multi_energy_is_available() -> None:
    response = client.post(
        "/fire-explosion-models/solve",
        json={
            "model_type": "multi_energy",
            "inputs": {
                "fuel_mass_kg": 300,
                "heat_of_combustion_kj_kg": 46000,
                "blast_strength": 6,
                "distance_m": 100,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert payload["equivalent_tnt_kg"] > 0
    assert payload["overpressure_kpa"] > 0


def test_effect_model_thermal_probit_returns_probability() -> None:
    response = client.post(
        "/effect-models/solve",
        json={
            "model_type": "thermal_probit",
            "inputs": {
                "heat_flux_kw_m2": 12.5,
                "exposure_time_s": 40,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["outputs"]
    assert 0 <= payload["burn_probability"] <= 1


def test_visualization_risk_contours_returns_geojson() -> None:
    response = client.post(
        "/visualization/solve",
        json={
            "layer_type": "risk_contours",
            "inputs": {
                "scenario_type": "fire",
                "source": {"latitude": 51.5074, "longitude": -0.1278, "label": "Source"},
                "zones": [
                    {
                        "label": "4 kW/m2",
                        "threshold": 4.0,
                        "unit": "kW/m^2",
                        "radius_m": 100.0,
                    }
                ],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["geojson"]["type"] == "FeatureCollection"
    assert any(feature["geometry"]["type"] == "Polygon" for feature in payload["geojson"]["features"])


def test_visualization_time_evolution_returns_frames() -> None:
    response = client.post(
        "/visualization/solve",
        json={
            "layer_type": "time_evolution",
            "inputs": {
                "source": {"latitude": 51.5074, "longitude": -0.1278},
                "max_radius_m": 250,
                "steps": 4,
                "frame_interval_s": 30,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["payload"]
    assert len(payload["frames"]) == 4
    assert payload["frames"][-1]["radius_m"] == 250.0


def test_visualization_heatmap_returns_grid_points() -> None:
    response = client.post(
        "/visualization/solve",
        json={
            "layer_type": "heatmap",
            "inputs": {
                "source": {"latitude": 51.5074, "longitude": -0.1278},
                "release_rate_kg_s": 2.0,
                "wind_speed_m_s": 3.0,
                "stability_class": "D",
                "x_distances_m": [50, 100],
                "y_offsets_m": [-50, 0, 50],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()["payload"]
    assert payload["layer_type"] == "heatmap"
    assert len(payload["points"]) == 6
