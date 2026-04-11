from __future__ import annotations

import math

from deepsafety.catalog import ModelInputError

TNT_HEAT_KJ_KG = 4_680.0


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


def solve_fire_explosion_model(model_type: str, payload: dict[str, object]) -> dict[str, object]:
    model_type = model_type.lower()
    if model_type == "jet_fire":
        return _solve_jet_fire(payload)
    if model_type == "pool_fire":
        return _solve_pool_fire(payload)
    if model_type == "fireball_bleve":
        return _solve_fireball(payload)
    if model_type == "tnt_equivalency":
        return _solve_tnt_equivalency(payload)
    if model_type == "multi_energy":
        return _solve_multi_energy(payload)
    if model_type == "vce":
        return _solve_vce(payload)
    raise ModelInputError(
        "Fire/explosion model must be one of jet_fire, pool_fire, fireball_bleve, tnt_equivalency, multi_energy, or vce."
    )


def _solve_jet_fire(payload: dict[str, object]) -> dict[str, object]:
    release_rate_kg_s = _positive_float(payload, "release_rate_kg_s")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    distance_m = _positive_float(payload, "distance_m")
    radiative_fraction = float(payload.get("radiative_fraction", 0.2))
    heat_flux_kw_m2 = (
        radiative_fraction * release_rate_kg_s * heat_of_combustion_kj_kg / (4 * math.pi * distance_m**2)
    )
    return {
        "model_type": "jet_fire",
        "heat_flux_kw_m2": round(heat_flux_kw_m2, 6),
        "flame_length_m": round(15 * release_rate_kg_s**0.4, 6),
    }


def _solve_pool_fire(payload: dict[str, object]) -> dict[str, object]:
    pool_area_m2 = _positive_float(payload, "pool_area_m2")
    burning_flux_kg_m2_s = _positive_float(payload, "burning_flux_kg_m2_s")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    distance_m = _positive_float(payload, "distance_m")
    radiative_fraction = float(payload.get("radiative_fraction", 0.35))
    burning_rate_kg_s = pool_area_m2 * burning_flux_kg_m2_s
    heat_flux_kw_m2 = (
        radiative_fraction * burning_rate_kg_s * heat_of_combustion_kj_kg / (4 * math.pi * distance_m**2)
    )
    return {
        "model_type": "pool_fire",
        "pool_diameter_m": round(math.sqrt(4 * pool_area_m2 / math.pi), 6),
        "burning_rate_kg_s": round(burning_rate_kg_s, 6),
        "heat_flux_kw_m2": round(heat_flux_kw_m2, 6),
    }


def _solve_fireball(payload: dict[str, object]) -> dict[str, object]:
    fuel_mass_kg = _positive_float(payload, "fuel_mass_kg")
    distance_m = _positive_float(payload, "distance_m")
    diameter_m = 5.8 * fuel_mass_kg**0.325
    duration_s = 0.45 * fuel_mass_kg**0.26
    radiative_fraction = float(payload.get("radiative_fraction", 0.35))
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    heat_flux_kw_m2 = (
        radiative_fraction
        * fuel_mass_kg
        * heat_of_combustion_kj_kg
        / max(1.0, duration_s)
        / (4 * math.pi * max(distance_m, 1.0) ** 2)
    )
    return {
        "model_type": "fireball_bleve",
        "fireball_diameter_m": round(diameter_m, 6),
        "fireball_duration_s": round(duration_s, 6),
        "heat_flux_kw_m2": round(heat_flux_kw_m2, 6),
    }


def _overpressure_from_scaled_distance(z: float) -> float:
    z = max(z, 0.05)
    return 1772 / z**3 + 114 / z**2 + 10.4 / z


def _solve_tnt_equivalency(payload: dict[str, object]) -> dict[str, object]:
    fuel_mass_kg = _positive_float(payload, "fuel_mass_kg")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    explosion_efficiency = float(payload.get("explosion_efficiency", 0.1))
    distance_m = _positive_float(payload, "distance_m")
    tnt_mass_kg = fuel_mass_kg * heat_of_combustion_kj_kg * explosion_efficiency / TNT_HEAT_KJ_KG
    scaled_distance = distance_m / max(tnt_mass_kg, 1e-6) ** (1 / 3)
    overpressure_kpa = _overpressure_from_scaled_distance(scaled_distance)
    return {
        "model_type": "tnt_equivalency",
        "tnt_equivalent_mass_kg": round(tnt_mass_kg, 6),
        "scaled_distance": round(scaled_distance, 6),
        "overpressure_kpa": round(overpressure_kpa, 6),
    }


def _solve_multi_energy(payload: dict[str, object]) -> dict[str, object]:
    fuel_mass_kg = _positive_float(payload, "fuel_mass_kg")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    blast_strength = float(payload.get("blast_strength", 5.0))
    distance_m = _positive_float(payload, "distance_m")
    equivalent_energy_kj = fuel_mass_kg * heat_of_combustion_kj_kg * blast_strength / 10
    equivalent_tnt_kg = equivalent_energy_kj / TNT_HEAT_KJ_KG
    scaled_distance = distance_m / max(equivalent_tnt_kg, 1e-6) ** (1 / 3)
    overpressure_kpa = _overpressure_from_scaled_distance(scaled_distance) * (blast_strength / 5)
    return {
        "model_type": "multi_energy",
        "equivalent_tnt_kg": round(equivalent_tnt_kg, 6),
        "scaled_distance": round(scaled_distance, 6),
        "overpressure_kpa": round(overpressure_kpa, 6),
    }


def _solve_vce(payload: dict[str, object]) -> dict[str, object]:
    cloud_mass_kg = _positive_float(payload, "cloud_mass_kg")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    ignition_delay_s = _positive_float(payload, "ignition_delay_s")
    congestion_factor = float(payload.get("congestion_factor", 1.0))
    distance_m = _positive_float(payload, "distance_m")
    yield_factor = min(0.3, 0.03 + 0.005 * ignition_delay_s + 0.05 * congestion_factor)
    tnt_mass_kg = cloud_mass_kg * heat_of_combustion_kj_kg * yield_factor / TNT_HEAT_KJ_KG
    scaled_distance = distance_m / max(tnt_mass_kg, 1e-6) ** (1 / 3)
    overpressure_kpa = _overpressure_from_scaled_distance(scaled_distance)
    return {
        "model_type": "vce",
        "yield_factor": round(yield_factor, 6),
        "tnt_equivalent_mass_kg": round(tnt_mass_kg, 6),
        "scaled_distance": round(scaled_distance, 6),
        "overpressure_kpa": round(overpressure_kpa, 6),
    }
