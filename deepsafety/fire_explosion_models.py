from __future__ import annotations

import math

from deepsafety.catalog import ModelInputError
from deepsafety.constants import get_constant_value

TNT_HEAT_KJ_KG = get_constant_value("shared.tnt_heat_of_explosion_kj_kg")
DEFAULT_FIRE_RADIATIVE_FRACTION = get_constant_value("fire.default_radiative_fraction")


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
    if model_type == "deflagration_screening":
        return _solve_deflagration(payload)
    if model_type == "detonation_screening":
        return _solve_detonation(payload)
    if model_type == "blast_damage_screening":
        return _solve_blast_damage(payload)
    if model_type == "mitigation_screening":
        return _solve_mitigation(payload)
    raise ModelInputError(
        "Fire/explosion model must be one of jet_fire, pool_fire, fireball_bleve, tnt_equivalency, "
        "multi_energy, vce, deflagration_screening, detonation_screening, "
        "blast_damage_screening, or mitigation_screening."
    )


def _solve_jet_fire(payload: dict[str, object]) -> dict[str, object]:
    release_rate_kg_s = _positive_float(payload, "release_rate_kg_s")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    distance_m = _positive_float(payload, "distance_m")
    radiative_fraction = float(payload.get("radiative_fraction", DEFAULT_FIRE_RADIATIVE_FRACTION))
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
    radiative_fraction = float(payload.get("radiative_fraction", DEFAULT_FIRE_RADIATIVE_FRACTION))
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
    radiative_fraction = float(payload.get("radiative_fraction", DEFAULT_FIRE_RADIATIVE_FRACTION))
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


def _solve_deflagration(payload: dict[str, object]) -> dict[str, object]:
    cloud_mass_kg = _positive_float(payload, "cloud_mass_kg")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    flame_speed_m_s = _positive_float(payload, "flame_speed_m_s")
    confinement_factor = float(payload.get("confinement_factor", 1.0))
    distance_m = _positive_float(payload, "distance_m")
    effective_efficiency = min(0.2, 0.02 + 0.0002 * flame_speed_m_s + 0.03 * confinement_factor)
    tnt_mass_kg = cloud_mass_kg * heat_of_combustion_kj_kg * effective_efficiency / TNT_HEAT_KJ_KG
    scaled_distance = distance_m / max(tnt_mass_kg, 1e-6) ** (1 / 3)
    overpressure_kpa = _overpressure_from_scaled_distance(scaled_distance)
    return {
        "model_type": "deflagration_screening",
        "effective_efficiency": round(effective_efficiency, 6),
        "tnt_equivalent_mass_kg": round(tnt_mass_kg, 6),
        "overpressure_kpa": round(overpressure_kpa, 6),
    }


def _solve_detonation(payload: dict[str, object]) -> dict[str, object]:
    cloud_mass_kg = _positive_float(payload, "cloud_mass_kg")
    heat_of_combustion_kj_kg = _positive_float(payload, "heat_of_combustion_kj_kg")
    detonable_fraction = float(payload.get("detonable_fraction", 0.3))
    distance_m = _positive_float(payload, "distance_m")
    if not 0 < detonable_fraction <= 1:
        raise ModelInputError("Input 'detonable_fraction' must be between 0 and 1.")
    tnt_mass_kg = cloud_mass_kg * heat_of_combustion_kj_kg * detonable_fraction / TNT_HEAT_KJ_KG
    scaled_distance = distance_m / max(tnt_mass_kg, 1e-6) ** (1 / 3)
    overpressure_kpa = _overpressure_from_scaled_distance(scaled_distance) * 1.3
    return {
        "model_type": "detonation_screening",
        "tnt_equivalent_mass_kg": round(tnt_mass_kg, 6),
        "overpressure_kpa": round(overpressure_kpa, 6),
        "detonation_likelihood": "credible" if detonable_fraction >= 0.25 else "screened_low",
    }


def _solve_blast_damage(payload: dict[str, object]) -> dict[str, object]:
    overpressure_kpa = _positive_float(payload, "overpressure_kpa")
    impulse_kpa_s = float(payload.get("impulse_kpa_s", 0.0))
    if overpressure_kpa >= 70:
        structural_damage = "severe"
    elif overpressure_kpa >= 35:
        structural_damage = "major"
    elif overpressure_kpa >= 14:
        structural_damage = "moderate"
    else:
        structural_damage = "minor"
    return {
        "model_type": "blast_damage_screening",
        "structural_damage": structural_damage,
        "window_breakage_likely": overpressure_kpa >= 3,
        "impulse_kpa_s": round(impulse_kpa_s, 6),
    }


def _solve_mitigation(payload: dict[str, object]) -> dict[str, object]:
    overpressure_kpa = _positive_float(payload, "overpressure_kpa")
    barrier_efficiency = float(payload.get("barrier_efficiency", 0.0))
    target_overpressure_kpa = _positive_float(payload, "target_overpressure_kpa")
    venting_factor = float(payload.get("venting_factor", 0.0))
    if not 0 <= barrier_efficiency <= 1:
        raise ModelInputError("Input 'barrier_efficiency' must be between 0 and 1.")
    if not 0 <= venting_factor <= 1:
        raise ModelInputError("Input 'venting_factor' must be between 0 and 1.")
    mitigated = overpressure_kpa * (1 - barrier_efficiency) * (1 - 0.5 * venting_factor)
    return {
        "model_type": "mitigation_screening",
        "mitigated_overpressure_kpa": round(mitigated, 6),
        "meets_target": mitigated <= target_overpressure_kpa,
        "required_additional_reduction_kpa": round(max(mitigated - target_overpressure_kpa, 0.0), 6),
    }
