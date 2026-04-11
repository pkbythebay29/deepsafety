from __future__ import annotations

from typing import Any

from deepsafety.catalog import ModelInputError
from deepsafety.materials_data import get_material_flammability


def _positive_float(payload: dict[str, Any], key: str) -> float:
    if key not in payload:
        raise ModelInputError(f"Missing required input '{key}'.")
    try:
        value = float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"Input '{key}' must be numeric.") from exc
    if value <= 0:
        raise ModelInputError(f"Input '{key}' must be greater than zero.")
    return value


def solve_purging_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    method = str(payload.get("method", "")).strip().lower()
    if method not in {
        "vacuum_purging",
        "pressure_purging",
        "pressure_vacuum_purging",
        "sweep_through",
        "siphon",
    }:
        raise ModelInputError("Input 'method' is not supported.")
    vessel_volume = _positive_float(payload, "vesselVolume")
    initial_oxygen = float(payload.get("initialOxygenPercent", 21.0))
    target_oxygen = float(payload.get("targetOxygenPercent", 8.0))
    purity = float(payload.get("purgeGasPurity", 0.99))
    if not 0 < purity <= 1:
        raise ModelInputError("Input 'purgeGasPurity' must be between 0 and 1.")
    removal_ratio = max(initial_oxygen / max(target_oxygen, 0.1), 1.0)
    method_factor = {
        "vacuum_purging": 0.6,
        "pressure_purging": 1.0,
        "pressure_vacuum_purging": 0.4,
        "sweep_through": 1.3,
        "siphon": 1.1,
    }[method]
    cycles = max(1, int(removal_ratio * method_factor))
    purge_gas_required = vessel_volume * cycles / purity
    return {
        "cyclesRequired": cycles,
        "purgeGasRequired": round(purge_gas_required, 6),
        "targetAchieved": True,
    }


def solve_static_electricity_risk(payload: dict[str, Any]) -> dict[str, Any]:
    conductivity = float(payload.get("conductivity", 0.0))
    flow_rate = float(payload.get("flowRate", 0.0))
    grounded = bool(payload.get("groundingBondingPresent", False))
    flammable = bool(payload.get("flammableAtmospherePresent", False))
    score = 0
    if conductivity < 1e-8:
        score += 2
    if flow_rate > 1:
        score += 1
    if not grounded:
        score += 2
    if flammable:
        score += 2
    if score >= 5:
        risk_level = "high"
    elif score >= 3:
        risk_level = "medium"
    else:
        risk_level = "low"
    recommendations = []
    if not grounded:
        recommendations.append("Add grounding and bonding to limit charge accumulation.")
    if conductivity < 1e-8:
        recommendations.append("Review conductivity improvement or additive strategy for the handled liquid.")
    if flammable:
        recommendations.append("Avoid operations in a flammable atmosphere or add inerting/ventilation.")
    return {"riskLevel": risk_level, "recommendations": recommendations}


def solve_area_classification(payload: dict[str, Any]) -> dict[str, Any]:
    zone_type = str(payload.get("zoneType", "secondary")).lower()
    ventilation_quality = str(payload.get("ventilationQuality", "fair")).lower()
    material_id = payload.get("materialId")
    flammable = get_material_flammability(str(material_id)) if material_id else {}
    if flammable.get("lfl") is None:
        classification = "nonhazardous_screening"
    elif zone_type == "continuous":
        classification = "zone_0_or_20_screening"
    elif zone_type == "primary":
        classification = "zone_1_or_21_screening"
    else:
        classification = "zone_2_or_22_screening" if ventilation_quality in {"good", "adequate"} else "zone_1_or_21_screening"
    return {
        "classification": classification,
        "notes": "Screening area classification is based on release grade and ventilation quality.",
    }


def solve_fire_protection_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    hazards = [str(item) for item in payload.get("hazards", [])]
    active = [str(item) for item in payload.get("activeSystems", [])]
    passive = [str(item) for item in payload.get("passiveSystems", [])]
    infrastructure = [str(item) for item in payload.get("infrastructure", [])]
    gaps = []
    if "pool_fire" in hazards and "foam" not in [item.lower() for item in active]:
        gaps.append("Pool fire hazard is present without foam-based active protection.")
    if "vce" in hazards and "blast_wall" not in [item.lower() for item in passive]:
        gaps.append("Explosion hazard is present without a passive blast-mitigation element in the starter review.")
    if "hydrant" not in [item.lower() for item in infrastructure]:
        gaps.append("Firewater access infrastructure is not listed.")
    summary = "Layer active, passive, and infrastructure measures around the listed hazards."
    return {"strategySummary": summary, "gaps": gaps}
