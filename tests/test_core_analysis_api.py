import uuid

from fastapi.testclient import TestClient

from deepsafety.api import create_app
from deepsafety.constants import get_constant_value
from deepsafety.data_access import get_connection, reset_runtime_caches


client = TestClient(create_app())


def _scenario_payload(name_suffix: str) -> dict[str, object]:
    return {
        "name": f"Scenario {name_suffix}",
        "description": "Workflow test scenario",
        "model_profile": {"domain": "integrated_consequence", "submodels": ["screening"], "units_system": "si"},
        "scenario_mode": "probabilistic",
        "inputs": {
            "inventory_mass_kg": {"kind": "scalar", "value": 1200.0, "unit": "kg"},
            "release_duration_s": {
                "kind": "scenario_triplet",
                "best_case": 30.0,
                "realistic_case": 60.0,
                "worst_case": 120.0,
                "unit": "s",
                "derived_distribution": "triangular",
            },
            "wind_speed_m_s": {
                "kind": "distribution",
                "distribution": {"type": "uniform", "min": 2.0, "max": 6.0},
                "unit": "m/s",
            },
        },
        "tags": ["workflow", "api"],
    }


def test_constants_are_loaded_from_database_registry() -> None:
    connection = get_connection()
    original = get_constant_value("fire.default_radiative_fraction")
    updated = round(original + 0.01, 6)
    connection.execute(
        "UPDATE constants SET value = ? WHERE name = ?",
        (updated, "fire.default_radiative_fraction"),
    )
    connection.commit()
    reset_runtime_caches()
    assert get_constant_value("fire.default_radiative_fraction") == updated

    connection.execute(
        "UPDATE constants SET value = ? WHERE name = ?",
        (original, "fire.default_radiative_fraction"),
    )
    connection.commit()
    reset_runtime_caches()
    assert get_constant_value("fire.default_radiative_fraction") == original


def test_scenario_workflow_supports_create_validate_patch_clone_and_versions() -> None:
    unique = uuid.uuid4().hex[:8]
    create_response = client.post("/scenarios", json=_scenario_payload(unique))
    assert create_response.status_code == 201
    scenario = create_response.json()
    assert scenario["status"] == "draft"
    assert scenario["etag"] == 'W/"1"'

    validation = client.post(f"/scenarios/{scenario['id']}/validate")
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert "release_duration_s" in validation.json()["normalized_inputs"]

    patch_response = client.patch(
        f"/scenarios/{scenario['id']}",
        headers={"If-Match": scenario["etag"]},
        json={"status": "active", "notes": "Activated for analysis"},
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["status"] == "active"
    assert updated["version"] == 2

    clone_response = client.post(
        f"/scenarios/{scenario['id']}/clone",
        json={"name": f"Scenario {unique} Clone", "include_tags": False},
    )
    assert clone_response.status_code == 201
    clone = clone_response.json()
    assert clone["name"].endswith("Clone")
    assert clone["tags"] == []

    versions_response = client.get(f"/scenarios/{scenario['id']}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()["items"]
    assert len(versions) >= 2
    assert versions[0]["version"] >= versions[-1]["version"]


def test_analysis_simulation_and_heatmap_workflow_returns_resources_and_jobs() -> None:
    scenario = client.post("/scenarios", json=_scenario_payload(uuid.uuid4().hex[:8])).json()

    analysis_submission = client.post(
        "/analyses",
        json={"scenario_id": scenario["id"], "analysis_type": "integrated_consequence", "outputs_of_interest": ["fatality_risk_index"]},
    )
    assert analysis_submission.status_code == 202
    analysis_job = client.get(f"/jobs/{analysis_submission.json()['job_id']}")
    assert analysis_job.status_code == 200
    assert analysis_job.json()["status"] == "completed"

    analysis = client.get(f"/analyses/{analysis_submission.json()['resource_id']}")
    assert analysis.status_code == 200
    analysis_payload = analysis.json()
    assert analysis_payload["summary"]["fatality_risk_index"] > 0

    simulation_submission = client.post(
        "/simulations",
        json={
            "scenario_id": scenario["id"],
            "sampling": {"method": "random", "iterations": 12, "seed": 7},
            "retain_samples": True,
        },
    )
    assert simulation_submission.status_code == 202
    simulation_id = simulation_submission.json()["resource_id"]

    simulation = client.get(f"/simulations/{simulation_id}")
    assert simulation.status_code == 200
    assert simulation.json()["summary"]

    samples = client.get(f"/simulations/{simulation_id}/samples?page_size=5")
    assert samples.status_code == 200
    assert len(samples.json()["items"]) == 5

    sensitivity = client.get(f"/simulations/{simulation_id}/sensitivity")
    assert sensitivity.status_code == 200
    assert sensitivity.json()["outputs"]

    heatmap_submission = client.post(
        "/heatmaps",
        json={
            "source": {"type": "analysis", "id": analysis_payload["id"]},
            "heatmap_type": "deterministic_value",
            "metric": "fatality_risk_index",
            "grid": {"x_min": -50, "x_max": 50, "y_min": -50, "y_max": 50, "dx": 25, "dy": 25},
        },
    )
    assert heatmap_submission.status_code == 202
    heatmap = client.get(f"/heatmaps/{heatmap_submission.json()['resource_id']}")
    assert heatmap.status_code == 200
    assert heatmap.json()["cells"]


def test_fault_tree_moc_and_report_workflow_endpoints_are_available() -> None:
    baseline = client.post("/scenarios", json=_scenario_payload(uuid.uuid4().hex[:8])).json()
    proposed_payload = _scenario_payload(uuid.uuid4().hex[:8])
    proposed_payload["inputs"]["inventory_mass_kg"]["value"] = 1800.0
    proposed = client.post("/scenarios", json=proposed_payload).json()

    fault_tree = client.post(
        "/fault-trees",
        json={
            "name": "Overpressure trip",
            "root": {
                "id": "root",
                "node_type": "gate",
                "gate_type": "or",
                "children": [
                    {"id": "a", "node_type": "basic_event", "probability": 0.2},
                    {"id": "b", "node_type": "basic_event", "probability": 0.4},
                ],
            },
        },
    )
    assert fault_tree.status_code == 201

    evaluation = client.post(
        f"/fault-trees/{fault_tree.json()['id']}/evaluate",
        json={"mode": "probabilistic", "iterations": 100},
    )
    assert evaluation.status_code == 202
    evaluation_job = client.get(f"/jobs/{evaluation.json()['job_id']}")
    assert evaluation_job.status_code == 200
    assert evaluation_job.json()["result_resource_id"]

    moc = client.post(
        "/mocs",
        json={
            "title": "Increase inventory",
            "change_type": "process_conditions",
            "baseline_scenario_id": baseline["id"],
            "proposed_scenario_id": proposed["id"],
        },
    )
    assert moc.status_code == 201
    moc_id = moc.json()["id"]

    submit = client.post(f"/mocs/{moc_id}/submit")
    assert submit.status_code == 200
    assert submit.json()["status"] == "submitted"

    screen = client.post(
        f"/mocs/{moc_id}/screen",
        json={"replacement_in_kind": False, "impacts": ["inventory", "pressure", "safeguards"]},
    )
    assert screen.status_code == 200
    assert screen.json()["requires_full_moc"] is True

    action = client.post(
        f"/mocs/{moc_id}/actions",
        json={"title": "Update operating envelope", "owner": "ops@example.com"},
    )
    assert action.status_code == 201

    action_update = client.patch(
        f"/mocs/{moc_id}/actions/{action.json()['id']}",
        headers={"If-Match": action.json()["etag"]},
        json={"status": "complete"},
    )
    assert action_update.status_code == 200
    assert action_update.json()["status"] == "complete"

    approval = client.post(f"/mocs/{moc_id}/approvals", json={"decision": "approve", "comment": "Proceed"})
    assert approval.status_code == 201
    assert approval.json()["decision"] == "approve"

    delta = client.post(
        f"/mocs/{moc_id}/delta-analysis",
        json={
            "baseline_scenario_id": baseline["id"],
            "proposed_scenario_id": proposed["id"],
            "analysis_type": "integrated_consequence",
        },
    )
    assert delta.status_code == 202

    close = client.post(f"/mocs/{moc_id}/close", json={"verification_notes": "Verified in commissioning"})
    assert close.status_code == 200
    assert close.json()["status"] == "closed"

    report_submission = client.post(
        "/reports",
        json={"report_type": "moc_delta", "source_type": "moc", "source_id": moc_id, "format": "json"},
    )
    assert report_submission.status_code == 202
    report = client.get(f"/reports/{report_submission.json()['resource_id']}")
    assert report.status_code == 200
    assert report.json()["download_url"].endswith(".json")
