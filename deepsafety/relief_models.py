from __future__ import annotations

import math
from typing import Any

from deepsafety.catalog import ModelInputError
from deepsafety.constants import get_constant_value


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


def select_relief_device(payload: dict[str, Any]) -> dict[str, Any]:
    service_type = str(payload.get("serviceType", "")).strip().lower()
    if service_type not in {"liquid", "gas", "vapor", "two_phase"}:
        raise ModelInputError("Input 'serviceType' is not supported.")
    cycling_expected = bool(payload.get("cyclingExpected", False))
    allowable_backpressure = float(payload.get("allowableBackpressure", 0.0))
    candidates = ["spring_operated"]
    if service_type in {"gas", "vapor"} and cycling_expected:
        candidates.insert(0, "pilot_operated")
    if allowable_backpressure < 0.1:
        candidates.append("rupture_disc")
    if service_type == "two_phase":
        candidates.append("buckling_pin")
    return {"candidates": list(dict.fromkeys(candidates))}


def analyze_relief_system(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = str(payload.get("scenario", "unknown"))
    vessel = dict(payload.get("vessel", {}))
    inventory = float(vessel.get("inventoryMassKg", vessel.get("inventory_mass_kg", 1000.0)))
    required_relief_load = inventory / 3600.0
    if "fire" in scenario.lower():
        required_relief_load *= 1.4
    return {
        "governingCase": scenario,
        "requiredReliefLoad": round(required_relief_load, 6),
        "notes": [
            "Relief load is a screening estimate based on vessel inventory and stated governing case."
        ],
    }


def select_effluent_handling(payload: dict[str, Any]) -> dict[str, Any]:
    state = str(payload.get("relievedMaterialState", "gas")).lower()
    toxic = bool(payload.get("toxic", False))
    flammable = bool(payload.get("flammable", False))
    if toxic:
        option = "scrubber"
    elif flammable and state in {"gas", "vapor"}:
        option = "flare"
    elif state == "liquid":
        option = "knockout_drum"
    else:
        option = "condenser"
    return {
        "recommendedOption": option,
        "rationale": "Screening selection is based on relieved phase together with toxic and flammable service flags.",
    }


def size_liquid_relief(payload: dict[str, Any]) -> dict[str, Any]:
    required_mass_rate = _positive_float(payload, "requiredMassRate")
    liquid_density = _positive_float(payload, "liquidDensity")
    set_pressure = float(payload.get("setPressure", 1_000_000.0))
    backpressure = float(payload.get("backpressure", 0.0))
    delta_p = max(set_pressure - backpressure, 1.0)
    discharge_coefficient = 0.62
    required_area = required_mass_rate / (discharge_coefficient * math.sqrt(2 * liquid_density * delta_p))
    return {
        "requiredArea": round(required_area, 8),
        "selectedOrificeArea": round(required_area * 1.1, 8),
        "governingAssumptions": ["Incompressible liquid screening relief equation."],
    }


def size_gas_vapor_relief(payload: dict[str, Any]) -> dict[str, Any]:
    required_mass_rate = _positive_float(payload, "requiredMassRate")
    temperature_k = _positive_float(payload, "temperatureK")
    molecular_weight = _positive_float(payload, "molecularWeight")
    heat_capacity_ratio = _positive_float(payload, "heatCapacityRatio")
    set_pressure = float(payload.get("setPressure", 1_000_000.0))
    backpressure = float(payload.get("backpressure", 101_325.0))
    delta_p = max(set_pressure - backpressure, 1.0)
    gas_constant = get_constant_value("shared.universal_gas_constant") / (molecular_weight / 1000.0)
    discharge_coefficient = 0.9
    required_area = required_mass_rate / (
        discharge_coefficient
        * max(set_pressure, 1.0)
        * math.sqrt(
            heat_capacity_ratio
            / (gas_constant * temperature_k)
            * (2 / (heat_capacity_ratio + 1)) ** ((heat_capacity_ratio + 1) / (heat_capacity_ratio - 1))
        )
    )
    return {
        "requiredArea": round(abs(required_area), 8),
        "selectedOrificeArea": round(abs(required_area) * 1.1, 8),
        "governingAssumptions": [f"Pressure differential screened at {round(delta_p, 2)} Pa."],
    }


def size_two_phase_relief(payload: dict[str, Any]) -> dict[str, Any]:
    required_mass_rate = _positive_float(payload, "requiredMassRate")
    quality = _positive_float(payload, "quality")
    required_area = required_mass_rate / max(25.0 * math.sqrt(quality + 0.1), 1e-6)
    return {
        "requiredArea": round(required_area, 8),
        "selectedOrificeArea": round(required_area * 1.15, 8),
        "governingAssumptions": ["Two-phase relief screening uses a quality-based capacity factor."],
    }


def size_external_fire_relief(payload: dict[str, Any]) -> dict[str, Any]:
    wetted_area = _positive_float(payload, "wettedArea")
    required_area = wetted_area * 2.5e-5
    return {
        "requiredArea": round(required_area, 8),
        "selectedOrificeArea": round(required_area * 1.1, 8),
        "governingAssumptions": ["External fire screening scales with wetted area."],
    }


def size_thermal_expansion_relief(payload: dict[str, Any]) -> dict[str, Any]:
    blocked_volume = _positive_float(payload, "blockedInVolume")
    coefficient = _positive_float(payload, "thermalExpansionCoefficient")
    temperature_rise = _positive_float(payload, "temperatureRise")
    required_area = blocked_volume * coefficient * temperature_rise * 1e-4
    return {
        "requiredArea": round(required_area, 8),
        "selectedOrificeArea": round(required_area * 1.1, 8),
        "governingAssumptions": ["Thermal expansion relief screening uses blocked volume expansion."],
    }


def size_deflagration_vent(payload: dict[str, Any]) -> dict[str, Any]:
    enclosure_volume = _positive_float(payload, "enclosureVolume")
    reduced_pressure_target = float(payload.get("reducedPressureTarget", 0.2))
    pmax = float(payload.get("pmax", 8.0))
    k_value = float(payload.get("kstOrKg", 150.0))
    required_vent_area = enclosure_volume ** (2 / 3) * (k_value / max(pmax * max(reduced_pressure_target, 0.05), 0.1)) * 0.1
    return {
        "requiredVentArea": round(required_vent_area, 8),
        "assumptions": [
            "Deflagration vent sizing uses a coarse enclosure volume and severity factor screening relation."
        ],
    }
