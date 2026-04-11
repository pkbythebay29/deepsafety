from __future__ import annotations

from typing import Any

from deepsafety.catalog import ModelInputError


def select_release_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    scenario_type = str(payload.get("scenarioType", "")).strip().lower()
    equipment_type = str(payload.get("equipmentType", "")).strip().lower()
    if scenario_type not in {"realistic", "worst_case"}:
        raise ModelInputError("Input 'scenarioType' must be 'realistic' or 'worst_case'.")
    if equipment_type not in {"pipe", "hose", "vessel", "relief_device", "tank"}:
        raise ModelInputError("Input 'equipmentType' is not supported.")

    if scenario_type == "worst_case":
        assumptions = {
            "releaseDurationS": 600.0,
            "releaseHeightM": 0.0,
            "windSpeedMps": 1.5,
            "stabilityClass": "F",
            "topography": payload.get("siteTopography", "urban"),
            "conservativeReasoning": "Worst-case release assumes prompt full inventory release over ten minutes unless constrained by the equipment form.",
        }
        if payload.get("inventoryMass") is not None:
            assumptions["inventoryMassKg"] = float(payload["inventoryMass"])
    else:
        diameter = float(payload.get("largestPipeDiameter", 0.05) or 0.05)
        assumptions = {
            "releaseDurationS": 180.0 if equipment_type in {"pipe", "hose"} else 300.0,
            "releaseHeightM": 0.0 if equipment_type in {"tank", "pipe"} else 2.0,
            "windSpeedMps": 3.0,
            "stabilityClass": "D",
            "credibleOpeningDiameterM": round(min(diameter, 0.25), 6),
            "topography": payload.get("siteTopography", "urban"),
            "conservativeReasoning": "Realistic release uses moderate meteorology and a credible opening rather than full-bore inventory loss by default.",
        }

    return {"assumptions": assumptions}


def apply_conservative_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    base_case = dict(payload.get("baseCase", {}))
    if not base_case:
        raise ModelInputError("Input 'baseCase' must be a non-empty object.")
    maximize = [str(item) for item in payload.get("maximize", [])]
    conservative_case = dict(base_case)
    rationale: list[str] = []

    if "release_duration" in maximize or "release_duration_s" in conservative_case:
        if "release_duration_s" in conservative_case:
            conservative_case["release_duration_s"] = max(float(conservative_case["release_duration_s"]), 600.0)
            rationale.append("Release duration was increased toward a conservative screening value.")
    if "wind_speed" in maximize and "wind_speed_m_s" in conservative_case:
        conservative_case["wind_speed_m_s"] = min(float(conservative_case["wind_speed_m_s"]), 1.5)
        rationale.append("Wind speed was lowered to increase downwind concentration conservatively.")
    if "stability" in maximize or "stability_class" in conservative_case:
        if "stability_class" in conservative_case:
            conservative_case["stability_class"] = "F"
            rationale.append("Atmospheric stability was shifted toward stable conditions.")
    if "inventory" in maximize and "inventory_mass_kg" in conservative_case:
        conservative_case["inventory_mass_kg"] = float(conservative_case["inventory_mass_kg"]) * 1.1
        rationale.append("Inventory mass was increased by ten percent for conservative screening.")
    if "hole_size" in maximize and "hole_diameter_m" in conservative_case:
        conservative_case["hole_diameter_m"] = float(conservative_case["hole_diameter_m"]) * 1.15
        rationale.append("Hole diameter was increased for conservative source-term screening.")

    conservative_case["conservative_mode"] = True
    if not rationale:
        rationale.append("Conservative mode flag was applied without changing specific dimensions.")
    return {
        "conservativeCase": conservative_case,
        "rationale": rationale,
    }
