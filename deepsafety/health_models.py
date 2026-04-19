from __future__ import annotations

import math
from typing import Any

from deepsafety.catalog import ModelInputError
from deepsafety.constants import get_constant_value
from deepsafety.materials_data import get_material


def _require_float(payload: dict[str, Any], key: str) -> float:
    if key not in payload:
        raise ModelInputError(f"Missing required input '{key}'.")
    try:
        return float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"Input '{key}' must be numeric.") from exc


def _positive_float(payload: dict[str, Any], key: str) -> float:
    value = _require_float(payload, key)
    if value <= 0:
        raise ModelInputError(f"Input '{key}' must be greater than zero.")
    return value


def convert_concentration(payload: dict[str, Any]) -> dict[str, Any]:
    value = _require_float(payload, "value")
    from_unit = str(payload.get("fromUnit", "")).strip().lower()
    to_unit = str(payload.get("toUnit", "")).strip().lower()
    temperature_k = _positive_float(payload, "temperatureK")
    pressure_atm = _positive_float(payload, "pressureAtm")
    molecular_weight = _positive_float(payload, "molecularWeight")

    if from_unit == to_unit:
        converted = value
    elif from_unit == "ppm" and to_unit == "mg/m3":
        converted = (
            value
            * molecular_weight
            * pressure_atm
            / (get_constant_value("shared.universal_gas_constant_atm_m3") * temperature_k)
            / 1e6
            * 1000
        )
    elif from_unit == "mg/m3" and to_unit == "ppm":
        converted = (
            value
            / 1000
            * get_constant_value("shared.universal_gas_constant_atm_m3")
            * temperature_k
            / (molecular_weight * pressure_atm)
            * 1e6
        )
    else:
        raise ModelInputError("Supported concentration units are ppm and mg/m3.")

    return {
        "inputValue": value,
        "outputValue": round(converted, 6),
        "outputUnit": payload.get("toUnit"),
    }


def evaluate_probit(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("probitValue") is not None:
        probit_value = float(payload["probitValue"])
    else:
        k1 = _require_float(payload, "k1")
        k2 = _require_float(payload, "k2")
        variable_value = _positive_float(payload, "variableValue")
        probit_value = k1 + k2 * math.log(variable_value)

    probability = 0.5 * (1 + math.erf((probit_value - 5.0) / math.sqrt(2)))
    return {
        "probitValue": round(probit_value, 6),
        "probability": round(probability, 6),
        "percentage": round(probability * 100, 6),
    }


def calculate_twa_exposure(payload: dict[str, Any]) -> dict[str, Any]:
    segments = payload.get("segments", [])
    if not isinstance(segments, list) or not segments:
        raise ModelInputError("Input 'segments' must be a non-empty list.")
    weighted_total = 0.0
    total_minutes = 0.0
    unit = None
    for segment in segments:
        if not isinstance(segment, dict):
            raise ModelInputError("Each exposure segment must be an object.")
        concentration = _positive_float(segment, "concentration")
        duration = _positive_float(segment, "durationMinutes")
        weighted_total += concentration * duration
        total_minutes += duration
        unit = segment.get("concentrationUnit", unit)
    return {
        "twa": round(weighted_total / total_minutes, 6),
        "durationMinutes": round(total_minutes, 6),
        "unit": unit or "ppm",
    }


def evaluate_exposure_compliance(payload: dict[str, Any]) -> dict[str, Any]:
    exposure_profile = payload.get("exposureProfile", {})
    criteria = payload.get("criteria", {})
    twa_result = calculate_twa_exposure(exposure_profile)
    twa = float(twa_result["twa"])
    results = []
    for criterion_name, limit in dict(criteria).items():
        if not isinstance(limit, dict) or "value" not in limit:
            raise ModelInputError(f"Criterion '{criterion_name}' must include a value and unit.")
        limit_value = float(limit["value"])
        results.append(
            {
                "criterion": criterion_name,
                "exceeded": twa > limit_value,
                "margin": round(limit_value - twa, 6),
            }
        )
    return {"results": results}


def calculate_dilution_ventilation(payload: dict[str, Any]) -> dict[str, Any]:
    generation_rate = _positive_float(payload, "generationRate")
    target_concentration = _positive_float(payload, "targetConcentration")
    room_conditions = payload.get("roomConditions", {})
    temperature_k = _positive_float(room_conditions, "temperatureK")
    pressure_atm = _positive_float(room_conditions, "pressureAtm")
    molecular_weight = float(room_conditions.get("molecularWeight", 28.97))
    mixing_factor = float(payload.get("mixingFactor", 1.0))

    target_unit = str(payload.get("targetUnit", "ppm")).lower()
    if target_unit == "ppm":
        target_mg_m3 = convert_concentration(
            {
                "value": target_concentration,
                "fromUnit": "ppm",
                "toUnit": "mg/m3",
                "temperatureK": temperature_k,
                "pressureAtm": pressure_atm,
                "molecularWeight": molecular_weight,
            }
        )["outputValue"]
    else:
        target_mg_m3 = target_concentration

    required_rate_m3_min = generation_rate / max(target_mg_m3, 1e-9) * max(mixing_factor, 1.0)
    return {
        "requiredVentilationRate": round(required_rate_m3_min / 60.0, 6),
        "unit": "m3/s",
    }


def calculate_local_exhaust(payload: dict[str, Any]) -> dict[str, Any]:
    capture_velocity = _positive_float(payload, "captureVelocity")
    hood_area = _positive_float(payload, "hoodArea")
    losses = float(payload.get("losses", 0.0))
    volumetric_flow = capture_velocity * hood_area * (1 + max(losses, 0.0))
    return {
        "volumetricFlowRate": round(volumetric_flow, 6),
        "unit": "m3/s",
    }


def estimate_pool_evaporation(payload: dict[str, Any]) -> dict[str, Any]:
    pool_area = _positive_float(payload, "poolArea")
    material = get_material(str(payload.get("materialId", "")))
    ambient = payload.get("ambient", {})
    temperature_k = _positive_float(ambient, "temperatureK")
    pressure_atm = _positive_float(ambient, "pressureAtm")
    wind_speed = _positive_float(ambient, "windSpeed")

    molecular_weight = float(material.get("molecularWeight") or 50.0)
    vapor_pressure = float(material.get("vaporPressure") or 101.325)
    volatility_factor = min(2.5, max(vapor_pressure / max(pressure_atm * 101.325, 1.0), 0.05))
    thermal_factor = max((temperature_k / 298.15), 0.5)
    evaporation_rate = 1e-4 * pool_area * wind_speed * volatility_factor * thermal_factor * math.sqrt(molecular_weight / 20.0)
    return {
        "evaporationRate": round(evaporation_rate, 6),
        "unit": "kg/s",
    }
