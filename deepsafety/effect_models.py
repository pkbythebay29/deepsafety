from __future__ import annotations

import math
from typing import Callable

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


def _positive_float_alias(payload: dict[str, object], *keys: str) -> float:
    for key in keys:
        if key in payload:
            return _positive_float(payload, key)
    joined = ", ".join(f"'{key}'" for key in keys)
    raise ModelInputError(f"Provide one of {joined}.")


def _optional_float(payload: dict[str, object], key: str, default: float) -> float:
    if key not in payload:
        return default
    try:
        return float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"Input '{key}' must be numeric.") from exc


def _probit_probability(probit_value: float) -> float:
    z_score = probit_value - 5.0
    return 0.5 * (1 + math.erf(z_score / math.sqrt(2)))


def _build_curve_values(
    payload: dict[str, object],
    explicit_key: str,
    min_key: str,
    max_key: str,
    points_key: str = "points",
) -> list[float]:
    if explicit_key in payload:
        values = payload[explicit_key]
        if not isinstance(values, list) or not values:
            raise ModelInputError(f"Input '{explicit_key}' must be a non-empty list.")
        try:
            parsed = [float(item) for item in values]
        except (TypeError, ValueError) as exc:
            raise ModelInputError(f"Input '{explicit_key}' must contain numeric values.") from exc
        if any(value <= 0 for value in parsed):
            raise ModelInputError(f"Input '{explicit_key}' values must be greater than zero.")
        return parsed

    lower = _positive_float(payload, min_key)
    upper = _positive_float(payload, max_key)
    points = int(payload.get(points_key, 9))
    if points < 2:
        raise ModelInputError(f"Input '{points_key}' must be at least 2.")
    if upper <= lower:
        raise ModelInputError(f"Input '{max_key}' must be greater than '{min_key}'.")
    step = (upper - lower) / (points - 1)
    return [lower + step * index for index in range(points)]


def _population_distribution(payload: dict[str, object]) -> list[dict[str, object]]:
    distribution = payload.get("population_distribution", [])
    if distribution in (None, []):
        population_count = _optional_float(payload, "population_count", 0.0)
        if population_count <= 0:
            return []
        return [
            {
                "id": "population",
                "label": "Population",
                "population": population_count,
            }
        ]

    if not isinstance(distribution, list):
        raise ModelInputError("Input 'population_distribution' must be a list of exposure records.")

    records: list[dict[str, object]] = []
    for index, item in enumerate(distribution, start=1):
        if not isinstance(item, dict):
            raise ModelInputError("Each population distribution item must be an object.")
        population = _positive_float(item, "population")
        records.append(
            {
                "id": str(item.get("id", f"zone-{index}")),
                "label": str(item.get("label", f"Zone {index}")),
                "population": population,
                **item,
            }
        )
    return records


def _summarize_population(
    records: list[dict[str, object]],
    probability_key: str,
    cases_key: str,
    metric_resolver: Callable[[dict[str, object]], dict[str, float]],
) -> dict[str, object]:
    if not records:
        return {
            "population_results": [],
            "population_total": 0.0,
            cases_key: 0.0,
            "maximum_probability": 0.0,
        }

    population_results: list[dict[str, object]] = []
    total_population = 0.0
    expected_cases = 0.0
    maximum_probability = 0.0

    for record in records:
        resolved = metric_resolver(record)
        population = float(record["population"])
        probability = resolved[probability_key]
        expected = probability * population
        total_population += population
        expected_cases += expected
        maximum_probability = max(maximum_probability, probability)
        population_results.append(
            {
                "id": record["id"],
                "label": record["label"],
                "population": round(population, 6),
                **{
                    key: round(value, 6)
                    for key, value in resolved.items()
                    if isinstance(value, float)
                },
                cases_key: round(expected, 6),
            }
        )

    return {
        "population_results": population_results,
        "population_total": round(total_population, 6),
        cases_key: round(expected_cases, 6),
        "maximum_probability": round(maximum_probability, 6),
    }


def solve_effect_model(model_type: str, payload: dict[str, object]) -> dict[str, object]:
    model_type = model_type.lower()
    if model_type == "toxic_probit":
        return _solve_toxic_probit(payload)
    if model_type == "toxic_dose_response":
        return _solve_toxic_dose_response(payload)
    if model_type == "thermal_probit":
        return _solve_thermal_probit(payload)
    if model_type == "thermal_dose_response":
        return _solve_thermal_dose_response(payload)
    if model_type == "explosion_probit":
        return _solve_explosion_probit(payload)
    if model_type == "explosion_dose_response":
        return _solve_explosion_dose_response(payload)
    raise ModelInputError(
        "Effect model must be one of toxic_probit, toxic_dose_response, thermal_probit, "
        "thermal_dose_response, explosion_probit, or explosion_dose_response."
    )


def _solve_toxic_probit(payload: dict[str, object]) -> dict[str, object]:
    concentration = _positive_float(payload, "concentration_kg_m3")
    exposure_time = _positive_float_alias(payload, "exposure_time_s", "exposure_duration_s")
    a = float(payload.get("a", -14.3))
    b = float(payload.get("b", 2.3))
    n = float(payload.get("n", 2.0))
    toxic_load = concentration**n * exposure_time
    probit_value = a + b * math.log(toxic_load)
    fatality_probability = _probit_probability(probit_value)

    population_summary = _summarize_population(
        _population_distribution(payload),
        "fatality_probability",
        "expected_fatalities",
        lambda record: _solve_toxic_probit(
            {
                "concentration_kg_m3": record.get("concentration_kg_m3", concentration),
                "exposure_time_s": record.get(
                    "exposure_time_s",
                    record.get("exposure_duration_s", exposure_time),
                ),
                "a": a,
                "b": b,
                "n": n,
            }
        ),
    )
    return {
        "model_type": "toxic_probit",
        "probit": round(probit_value, 6),
        "fatality_probability": round(fatality_probability, 6),
        "toxic_load": round(toxic_load, 6),
        **population_summary,
    }


def _solve_toxic_dose_response(payload: dict[str, object]) -> dict[str, object]:
    exposure_time = _positive_float_alias(payload, "exposure_time_s", "exposure_duration_s")
    a = float(payload.get("a", -14.3))
    b = float(payload.get("b", 2.3))
    n = float(payload.get("n", 2.0))
    concentrations = _build_curve_values(
        payload,
        "concentrations_kg_m3",
        "min_concentration_kg_m3",
        "max_concentration_kg_m3",
    )
    curve = []
    for concentration in concentrations:
        result = _solve_toxic_probit(
            {
                "concentration_kg_m3": concentration,
                "exposure_time_s": exposure_time,
                "a": a,
                "b": b,
                "n": n,
            }
        )
        curve.append(
            {
                "concentration_kg_m3": round(concentration, 6),
                "probit": result["probit"],
                "fatality_probability": result["fatality_probability"],
                "toxic_load": result["toxic_load"],
            }
        )
    return {
        "model_type": "toxic_dose_response",
        "exposure_time_s": round(exposure_time, 6),
        "curve": curve,
    }


def _solve_thermal_probit(payload: dict[str, object]) -> dict[str, object]:
    heat_flux = _positive_float_alias(payload, "heat_flux_kw_m2", "radiation_kw_m2")
    exposure_time = _positive_float_alias(payload, "exposure_time_s", "exposure_duration_s")
    a = float(payload.get("a", -36.38))
    b = float(payload.get("b", 2.56))
    thermal_load = heat_flux ** (4 / 3) * exposure_time
    probit_value = a + b * math.log(thermal_load)
    burn_probability = _probit_probability(probit_value)

    population_summary = _summarize_population(
        _population_distribution(payload),
        "burn_probability",
        "expected_burn_cases",
        lambda record: _solve_thermal_probit(
            {
                "heat_flux_kw_m2": record.get(
                    "heat_flux_kw_m2",
                    record.get("radiation_kw_m2", heat_flux),
                ),
                "exposure_time_s": record.get(
                    "exposure_time_s",
                    record.get("exposure_duration_s", exposure_time),
                ),
                "a": a,
                "b": b,
            }
        ),
    )
    return {
        "model_type": "thermal_probit",
        "probit": round(probit_value, 6),
        "burn_probability": round(burn_probability, 6),
        "thermal_load": round(thermal_load, 6),
        **population_summary,
    }


def _solve_thermal_dose_response(payload: dict[str, object]) -> dict[str, object]:
    exposure_time = _positive_float_alias(payload, "exposure_time_s", "exposure_duration_s")
    a = float(payload.get("a", -36.38))
    b = float(payload.get("b", 2.56))
    heat_fluxes = _build_curve_values(
        payload,
        "heat_fluxes_kw_m2",
        "min_heat_flux_kw_m2",
        "max_heat_flux_kw_m2",
    )
    curve = []
    for heat_flux in heat_fluxes:
        result = _solve_thermal_probit(
            {
                "heat_flux_kw_m2": heat_flux,
                "exposure_time_s": exposure_time,
                "a": a,
                "b": b,
            }
        )
        curve.append(
            {
                "heat_flux_kw_m2": round(heat_flux, 6),
                "probit": result["probit"],
                "burn_probability": result["burn_probability"],
                "thermal_load": result["thermal_load"],
            }
        )
    return {
        "model_type": "thermal_dose_response",
        "exposure_time_s": round(exposure_time, 6),
        "curve": curve,
    }


def _solve_explosion_probit(payload: dict[str, object]) -> dict[str, object]:
    overpressure_kpa = _positive_float(payload, "overpressure_kpa")
    a = float(payload.get("a", -77.1))
    b = float(payload.get("b", 6.91))
    overpressure_pa = overpressure_kpa * 1000.0
    probit_value = a + b * math.log(overpressure_pa)
    fatality_probability = _probit_probability(probit_value)

    population_summary = _summarize_population(
        _population_distribution(payload),
        "fatality_probability",
        "expected_fatalities",
        lambda record: _solve_explosion_probit(
            {
                "overpressure_kpa": record.get("overpressure_kpa", overpressure_kpa),
                "a": a,
                "b": b,
            }
        ),
    )
    return {
        "model_type": "explosion_probit",
        "probit": round(probit_value, 6),
        "fatality_probability": round(fatality_probability, 6),
        **population_summary,
    }


def _solve_explosion_dose_response(payload: dict[str, object]) -> dict[str, object]:
    a = float(payload.get("a", -77.1))
    b = float(payload.get("b", 6.91))
    overpressures = _build_curve_values(
        payload,
        "overpressures_kpa",
        "min_overpressure_kpa",
        "max_overpressure_kpa",
    )
    curve = []
    for overpressure in overpressures:
        result = _solve_explosion_probit(
            {
                "overpressure_kpa": overpressure,
                "a": a,
                "b": b,
            }
        )
        curve.append(
            {
                "overpressure_kpa": round(overpressure, 6),
                "probit": result["probit"],
                "fatality_probability": result["fatality_probability"],
            }
        )
    return {
        "model_type": "explosion_dose_response",
        "curve": curve,
    }
