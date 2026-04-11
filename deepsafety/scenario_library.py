from __future__ import annotations

SCENARIO_TEMPLATES: list[dict[str, object]] = [
    {
        "id": "tank_rupture",
        "name": "Tank Rupture",
        "incident_type": "tank_leak",
        "summary": "Atmospheric or low-pressure storage tank loss of containment.",
        "default_inventory": {"phase": "liquid", "mass_kg": 20_000},
        "default_equipment": {"type": "tank", "diameter_m": 12.0, "height_m": 10.0},
        "default_failure_mode": "catastrophic_wall_failure",
        "recommended_services": ["source", "dispersion", "fire_explosion", "effects"],
    },
    {
        "id": "pipeline_leak",
        "name": "Pipeline Leak",
        "incident_type": "pipe_rupture",
        "summary": "Pressurized line leak or rupture for gas or liquid service.",
        "default_inventory": {"phase": "gas", "mass_kg": 5_000},
        "default_equipment": {"type": "pipe", "diameter_m": 0.25, "length_m": 500.0},
        "default_failure_mode": "full_bore_rupture",
        "recommended_services": ["source", "dispersion", "effects", "visualization"],
    },
    {
        "id": "bleve",
        "name": "BLEVE",
        "incident_type": "vessel_rupture",
        "summary": "Pressurized vessel rupture with fireball potential.",
        "default_inventory": {"phase": "two_phase", "mass_kg": 10_000},
        "default_equipment": {"type": "vessel", "volume_m3": 40.0},
        "default_failure_mode": "catastrophic_rupture",
        "recommended_services": ["source", "fire_explosion", "effects", "visualization"],
    },
    {
        "id": "toxic_gas_release",
        "name": "Toxic Gas Release",
        "incident_type": "relief_discharge",
        "summary": "Toxic gas release to atmosphere with offsite consequence focus.",
        "default_inventory": {"phase": "gas", "mass_kg": 2_000},
        "default_equipment": {"type": "relief_system", "diameter_m": 0.05},
        "default_failure_mode": "relief_valve_lift",
        "recommended_services": ["source", "dispersion", "effects", "visualization"],
    },
]


def list_templates() -> list[dict[str, object]]:
    return SCENARIO_TEMPLATES
