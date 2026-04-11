from fastapi.testclient import TestClient

from deepsafety.api import create_app


client = TestClient(create_app())


def test_material_endpoints_expose_foundational_data() -> None:
    listing = client.get("/materials?q=ammonia")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["total"] >= 1
    assert any(item["id"] == "ammonia" for item in payload["items"])

    detail = client.get("/materials/ammonia")
    assert detail.status_code == 200
    assert detail.json()["flammability"]["lfl"] == 15.0

    toxicity = client.get("/materials/ammonia/toxicity")
    assert toxicity.status_code == 200
    assert toxicity.json()["materialId"] == "ammonia"


def test_health_and_industrial_hygiene_endpoints_work() -> None:
    conversion = client.post(
        "/health/convert-concentration",
        json={
            "value": 25,
            "fromUnit": "ppm",
            "toUnit": "mg/m3",
            "temperatureK": 298.15,
            "pressureAtm": 1.0,
            "molecularWeight": 17.031,
        },
    )
    assert conversion.status_code == 200
    assert conversion.json()["outputValue"] > 0

    ventilation = client.post(
        "/industrial-hygiene/ventilation/dilution",
        json={
            "generationRate": 12.0,
            "targetConcentration": 25.0,
            "targetUnit": "ppm",
            "roomConditions": {"temperatureK": 298.15, "pressureAtm": 1.0, "molecularWeight": 17.031},
        },
    )
    assert ventilation.status_code == 200
    assert ventilation.json()["requiredVentilationRate"] > 0


def test_spec_source_model_routes_return_expected_shapes() -> None:
    gas_hole = client.post(
        "/source-models/gas-hole",
        json={
            "upstreamPressure": 5_000_000,
            "downstreamPressure": 101_325,
            "temperatureK": 288.15,
            "molecularWeight": 16.04,
            "heatCapacityRatio": 1.3,
            "holeArea": 1.0e-4,
        },
    )
    assert gas_hole.status_code == 200
    assert gas_hole.json()["massFlowRate"] > 0

    scenario = client.post(
        "/source-models/scenario/select",
        json={"scenarioType": "worst_case", "equipmentType": "pipe", "inventoryMass": 500},
    )
    assert scenario.status_code == 200
    assert scenario.json()["assumptions"]["releaseDurationS"] == 600.0

    conservative = client.post(
        "/source-models/conservative-analysis",
        json={"baseCase": {"wind_speed_m_s": 3.0, "stability_class": "D"}, "maximize": ["wind_speed", "stability"]},
    )
    assert conservative.status_code == 200
    assert conservative.json()["conservativeCase"]["stability_class"] == "F"


def test_spec_dispersion_routes_support_result_workflow() -> None:
    plume = client.post(
        "/dispersion/gaussian-plume",
        json={
            "releaseRate": 2.0,
            "releaseHeight": 0.0,
            "windSpeed": 3.0,
            "stabilityClass": "D",
            "receptorGrid": {"xMin": 50, "xMax": 150, "yMin": -25, "yMax": 25, "dx": 50, "dy": 25, "z": 0},
        },
    )
    assert plume.status_code == 200
    plume_payload = plume.json()
    assert plume_payload["resultId"]
    assert plume_payload["maxConcentration"] > 0

    isopleth = client.post(
        "/dispersion/isopleth",
        json={"dispersionResultId": plume_payload["resultId"], "threshold": plume_payload["maxConcentration"] * 0.5},
    )
    assert isopleth.status_code == 200
    assert "boundary" in isopleth.json()


def test_fire_explosion_spec_routes_are_available() -> None:
    mixture = client.post(
        "/fire-explosion/flammability/mixture",
        json={
            "components": [
                {"materialId": "methane", "moleFraction": 0.6},
                {"materialId": "propane", "moleFraction": 0.4},
            ],
            "oxygenFraction": 0.21,
        },
    )
    assert mixture.status_code == 200
    assert mixture.json()["estimatedLfl"] is not None

    loc = client.post(
        "/fire-explosion/loc",
        json={"fuelSystem": {"components": [{"materialId": "methane", "moleFraction": 1.0}]}, "operatingOxygenPercent": 10.0},
    )
    assert loc.status_code == 200
    assert loc.json()["safe"] is True

    vce = client.post(
        "/fire-explosion/vce",
        json={"releasedMass": 800, "vaporizedFraction": 0.5, "congestionLevel": "high", "delayedIgnition": True},
    )
    assert vce.status_code == 200
    assert vce.json()["tntEquivalentMass"] > 0
    assert vce.json()["overpressureProfile"]["points"]


def test_prevention_reactivity_relief_and_hazard_routes_are_available() -> None:
    purge = client.post(
        "/prevention/inerting/purge",
        json={"method": "vacuum_purging", "vesselVolume": 20.0, "initialOxygenPercent": 21.0, "targetOxygenPercent": 8.0},
    )
    assert purge.status_code == 200
    assert purge.json()["cyclesRequired"] >= 1

    reactivity = client.post(
        "/reactivity/screening",
        json={"materials": ["ammonia", "chlorine"], "processConditions": {"temperatureC": 25}},
    )
    assert reactivity.status_code == 200
    assert reactivity.json()["reactiveHazardPresent"] is True

    relief = client.post(
        "/relief/sizing/gas-vapor",
        json={
            "requiredMassRate": 2.0,
            "temperatureK": 320.0,
            "molecularWeight": 18.0,
            "heatCapacityRatio": 1.3,
            "setPressure": 800_000.0,
            "backpressure": 101_325.0,
        },
    )
    assert relief.status_code == 200
    assert relief.json()["requiredArea"] > 0

    hazop = client.post(
        "/hazard-evaluation/what-if-checklist",
        json={"processId": "unit-1", "prompts": ["What if isolation fails?"], "checklistItems": ["Relief path blocked"]},
    )
    assert hazop.status_code == 200
    assert len(hazop.json()["findings"]) == 2

    validation = client.post(
        "/hazard-evaluation/information-requirements/validate",
        json={"chemicals": {"flammability": {}, "toxicity": {}, "reactivity": {}, "physical_properties": {}}, "equipment": {}, "procedures": {}, "conditions": {"temperature": 25, "pressure": 2, "flow": 1}},
    )
    assert validation.status_code == 200
    assert validation.json()["complete"] is False
