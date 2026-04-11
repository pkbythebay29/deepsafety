from __future__ import annotations

from typing import Any

from deepsafety.catalog import ModelInputError
from deepsafety.materials_data import get_material_reactivity


def interpret_calorimetry(payload: dict[str, Any]) -> dict[str, Any]:
    dataset = dict(payload.get("dataset", {}))
    heat_flow_w = float(dataset.get("heatFlowW", dataset.get("heat_flow_w", 0.0)))
    duration_s = float(dataset.get("durationS", dataset.get("duration_s", 0.0)))
    mass_kg = float(dataset.get("massKg", dataset.get("mass_kg", 1.0)) or 1.0)
    if heat_flow_w <= 0 or duration_s <= 0:
        raise ModelInputError("Calorimetry dataset must include positive heat flow and duration.")
    correction = 1.1 if payload.get("vesselHeatCapacityCorrection") else 1.0
    heat_of_reaction = heat_flow_w * duration_s * correction / max(mass_kg, 1e-6)
    return {
        "heatOfReaction": round(heat_of_reaction, 6),
        "adjustedData": {
            **dataset,
            "appliedCorrectionFactor": correction,
        },
        "warnings": [
            "This is a screening interpretation, not a full calorimetry data reduction workflow."
        ],
    }


def screen_reactivity(payload: dict[str, Any]) -> dict[str, Any]:
    materials = [str(item) for item in payload.get("materials", [])]
    if not materials:
        raise ModelInputError("Input 'materials' must be a non-empty list.")
    contaminants = [str(item) for item in payload.get("contaminants", [])]
    process_conditions = dict(payload.get("processConditions", {}))
    scenarios = []
    data_gaps = []
    for material_id in materials:
        profile = get_material_reactivity(material_id)
        incompatibilities = [item.lower() for item in profile.get("incompatibilities", [])]
        for other in materials + contaminants:
            if other.lower() in incompatibilities:
                scenarios.append(f"Potential reactive incompatibility between {material_id} and {other}.")
        if not profile.get("calorimetryAvailable"):
            data_gaps.append(f"No calorimetry interpretation data is flagged for {material_id}.")
    if float(process_conditions.get("temperatureC", 25.0)) > 150:
        scenarios.append("Elevated process temperature may accelerate reactive decomposition or incompatibility severity.")
    return {
        "reactiveHazardPresent": bool(scenarios),
        "scenarios": scenarios,
        "dataGaps": data_gaps,
    }


def recommend_reactivity_controls(payload: dict[str, Any]) -> dict[str, Any]:
    hazard_summary = dict(payload.get("hazardSummary", {}))
    control_preferences = [str(item).lower() for item in payload.get("controlPreferences", [])]
    controls = []
    if hazard_summary.get("reactiveHazardPresent"):
        controls.extend(
            [
                "Segregate incompatible materials and review charging procedures.",
                "Add calorimetry or reaction screening before scale-up.",
                "Provide emergency quench or cooling where runaway escalation is credible.",
            ]
        )
    if "inerting" in control_preferences:
        controls.append("Consider inerting if oxidation or flammable reactive pathways are part of the hazard.")
    if "temperature_control" in control_preferences:
        controls.append("Tighten temperature interlocks and high-temperature shutdown setpoints.")
    return {"recommendedControls": controls}
