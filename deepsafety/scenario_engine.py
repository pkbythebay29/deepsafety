from __future__ import annotations

from copy import deepcopy

from deepsafety.catalog import ModelInputError
from deepsafety.scenario_library import list_templates


EPA_WORST_CASE_REFERENCES = [
    {
        "title": "EPA Offsite Consequence Analysis worst-case assumptions",
        "url": "https://www.epa.gov/rmp/general-rmp-guidance-chapter-4-offsite-consequence-analysis",
        "notes": "Used for 10-minute release, ground-level release, and default worst-case meteorology assumptions.",
    },
    {
        "title": "40 CFR 68 Appendix A",
        "url": "https://www.epa.gov/sites/default/files/2013-11/documents/appendix-a-final.pdf",
        "notes": "Worst-case toxic gas release assumptions include total vessel or pipe quantity released over 10 minutes.",
    },
]


INCIDENT_DEFAULTS = {
    "pipe_rupture": {
        "failure_mode": "full_bore_rupture",
        "equipment_type": "pipe",
    },
    "tank_leak": {
        "failure_mode": "wall_or_bottom_leak",
        "equipment_type": "tank",
    },
    "vessel_rupture": {
        "failure_mode": "catastrophic_rupture",
        "equipment_type": "vessel",
    },
    "relief_discharge": {
        "failure_mode": "relief_valve_discharge",
        "equipment_type": "relief_system",
    },
}


CLASSIFICATION_DEFAULTS = {
    "worst_case": {
        "release_duration_s": 600.0,
        "release_height_m": 0.0,
        "meteorology": {
            "wind_speed_m_s": 1.5,
            "stability_class": "F",
            "ambient_temperature_c": 25.0,
            "relative_humidity_percent": 50.0,
        },
        "topography": "urban",
        "assumption_set": "epa_worst_case_screening",
    },
    "realistic_case": {
        "release_duration_s": 300.0,
        "release_height_m": 2.0,
        "meteorology": {
            "wind_speed_m_s": 3.0,
            "stability_class": "D",
            "ambient_temperature_c": 25.0,
            "relative_humidity_percent": 50.0,
        },
        "topography": "urban",
        "assumption_set": "screening_realistic_case",
    },
}


def _merge_dict(base: dict[str, object], overrides: dict[str, object]) -> dict[str, object]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def build_scenario_definition(payload: dict[str, object]) -> dict[str, object]:
    incident_type = str(payload.get("incident_type", "")).strip().lower()
    classification = str(payload.get("classification", "")).strip().lower()
    if incident_type not in INCIDENT_DEFAULTS:
        raise ModelInputError(
            "Incident type must be one of pipe_rupture, tank_leak, vessel_rupture, or relief_discharge."
        )
    if classification not in CLASSIFICATION_DEFAULTS:
        raise ModelInputError(
            "Scenario classification must be one of realistic_case or worst_case."
        )

    incident_defaults = INCIDENT_DEFAULTS[incident_type]
    classification_defaults = CLASSIFICATION_DEFAULTS[classification]
    meteorology = _merge_dict(
        classification_defaults["meteorology"], payload.get("meteorology", {})
    )

    inventory = dict(payload.get("inventory", {}))
    equipment = dict(payload.get("equipment", {}))
    if "type" not in equipment:
        equipment["type"] = incident_defaults["equipment_type"]

    scenario = {
        "incident_type": incident_type,
        "classification": classification,
        "inventory": inventory,
        "equipment": equipment,
        "failure_mode": payload.get("failure_mode", incident_defaults["failure_mode"]),
        "meteorology": meteorology,
        "release_height_m": payload.get(
            "release_height_m", classification_defaults["release_height_m"]
        ),
        "topography": payload.get("topography", classification_defaults["topography"]),
        "release_duration_s": payload.get(
            "release_duration_s", classification_defaults["release_duration_s"]
        ),
        "conservative_mode": bool(payload.get("conservative_mode", False)),
        "assumption_set": classification_defaults["assumption_set"],
        "references": EPA_WORST_CASE_REFERENCES if classification == "worst_case" else [],
        "available_templates": [template["id"] for template in list_templates()],
    }

    return scenario
