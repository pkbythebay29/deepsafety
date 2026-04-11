from __future__ import annotations

import math

from deepsafety.catalog import ModelInputError


def _require_float(payload: dict[str, object], key: str) -> float:
    if key not in payload:
        raise ModelInputError(f"Missing required input '{key}'.")
    try:
        return float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"Input '{key}' must be numeric.") from exc


def _positive_float(payload: dict[str, object], key: str) -> float:
    value = _require_float(payload, key)
    if value <= 0:
        raise ModelInputError(f"Input '{key}' must be greater than zero.")
    return value


def _probit_probability(probit_value: float) -> float:
    z_score = probit_value - 5.0
    return 0.5 * (1 + math.erf(z_score / math.sqrt(2)))


def solve_effect_model(model_type: str, payload: dict[str, object]) -> dict[str, object]:
    model_type = model_type.lower()
    if model_type == "toxic_probit":
        return _solve_toxic_probit(payload)
    if model_type == "thermal_probit":
        return _solve_thermal_probit(payload)
    if model_type == "explosion_probit":
        return _solve_explosion_probit(payload)
    raise ModelInputError(
        "Effect model must be one of toxic_probit, thermal_probit, or explosion_probit."
    )


def _solve_toxic_probit(payload: dict[str, object]) -> dict[str, object]:
    concentration = _positive_float(payload, "concentration_kg_m3")
    exposure_time = _positive_float(payload, "exposure_time_s")
    a = float(payload.get("a", -14.3))
    b = float(payload.get("b", 2.3))
    n = float(payload.get("n", 2.0))
    toxic_load = concentration**n * exposure_time
    probit_value = a + b * math.log(toxic_load)
    return {
        "model_type": "toxic_probit",
        "probit": round(probit_value, 6),
        "fatality_probability": round(_probit_probability(probit_value), 6),
        "toxic_load": round(toxic_load, 6),
    }


def _solve_thermal_probit(payload: dict[str, object]) -> dict[str, object]:
    heat_flux = _positive_float(payload, "heat_flux_kw_m2")
    exposure_time = _positive_float(payload, "exposure_time_s")
    a = float(payload.get("a", -36.38))
    b = float(payload.get("b", 2.56))
    thermal_load = heat_flux ** (4 / 3) * exposure_time
    probit_value = a + b * math.log(thermal_load)
    return {
        "model_type": "thermal_probit",
        "probit": round(probit_value, 6),
        "burn_probability": round(_probit_probability(probit_value), 6),
        "thermal_load": round(thermal_load, 6),
    }


def _solve_explosion_probit(payload: dict[str, object]) -> dict[str, object]:
    overpressure_kpa = _positive_float(payload, "overpressure_kpa")
    a = float(payload.get("a", -77.1))
    b = float(payload.get("b", 6.91))
    overpressure_pa = overpressure_kpa * 1000.0
    probit_value = a + b * math.log(overpressure_pa)
    return {
        "model_type": "explosion_probit",
        "probit": round(probit_value, 6),
        "fatality_probability": round(_probit_probability(probit_value), 6),
    }
