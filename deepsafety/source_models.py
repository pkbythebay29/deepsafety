from __future__ import annotations

import math

from deepsafety.catalog import ModelInputError

GRAVITY = 9.80665
UNIVERSAL_GAS_CONSTANT = 8.314462618


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


def _area_from_payload(payload: dict[str, object]) -> float:
    if "area_m2" in payload:
        return _positive_float(payload, "area_m2")
    diameter = _positive_float(payload, "diameter_m")
    return math.pi * diameter**2 / 4


def solve_source_model(model_type: str, payload: dict[str, object]) -> dict[str, object]:
    conservative_mode = bool(payload.get("conservative_mode", False))
    model_type = model_type.lower()
    if model_type == "gas_release":
        return _solve_gas_release(payload, conservative_mode)
    if model_type == "liquid_release":
        return _solve_liquid_release(payload, conservative_mode)
    if model_type == "flashing":
        return _solve_flashing(payload)
    if model_type == "pool_formation":
        return _solve_pool_formation(payload)
    if model_type == "evaporation":
        return _solve_evaporation(payload)
    raise ModelInputError(
        "Source model must be one of gas_release, liquid_release, flashing, pool_formation, or evaporation."
    )


def _solve_gas_release(payload: dict[str, object], conservative_mode: bool) -> dict[str, object]:
    area_m2 = _area_from_payload(payload)
    upstream_pressure_pa = _positive_float(payload, "upstream_pressure_pa")
    downstream_pressure_pa = _positive_float(payload, "downstream_pressure_pa")
    temperature_k = _positive_float(payload, "temperature_k")
    heat_capacity_ratio = _positive_float(payload, "heat_capacity_ratio")
    molecular_weight = _positive_float(payload, "molecular_weight_kg_kmol") / 1000.0
    discharge_coefficient = float(payload.get("discharge_coefficient", 0.62))
    compressibility = float(payload.get("compressibility", 1.0))
    duration_s = _positive_float(payload, "duration_s")

    specific_gas_constant = UNIVERSAL_GAS_CONSTANT / molecular_weight
    pressure_ratio = downstream_pressure_pa / upstream_pressure_pa
    critical_ratio = (2 / (heat_capacity_ratio + 1)) ** (
        heat_capacity_ratio / (heat_capacity_ratio - 1)
    )
    choked = pressure_ratio <= critical_ratio

    if choked:
        mass_rate = (
            discharge_coefficient
            * area_m2
            * upstream_pressure_pa
            * math.sqrt(
                heat_capacity_ratio
                / (compressibility * specific_gas_constant * temperature_k)
                * (2 / (heat_capacity_ratio + 1))
                ** ((heat_capacity_ratio + 1) / (heat_capacity_ratio - 1))
            )
        )
    else:
        mass_rate = (
            discharge_coefficient
            * area_m2
            * upstream_pressure_pa
            * math.sqrt(
                (2 * heat_capacity_ratio)
                / (compressibility * specific_gas_constant * temperature_k * (heat_capacity_ratio - 1))
                * (
                    pressure_ratio ** (2 / heat_capacity_ratio)
                    - pressure_ratio ** ((heat_capacity_ratio + 1) / heat_capacity_ratio)
                )
            )
        )

    if conservative_mode:
        mass_rate *= 1.15

    total_mass = mass_rate * duration_s
    return {
        "model_type": "gas_release",
        "submodel": "choked_flow" if choked else "non_choked_compressible_flow",
        "discharge_geometry": payload.get("discharge_geometry", "hole"),
        "release_rate_kg_s": round(mass_rate, 6),
        "total_mass_kg": round(total_mass, 6),
        "phase_state": "gas",
        "critical_pressure_ratio": round(critical_ratio, 6),
    }


def _solve_liquid_release(payload: dict[str, object], conservative_mode: bool) -> dict[str, object]:
    area_m2 = _area_from_payload(payload)
    density_kg_m3 = _positive_float(payload, "density_kg_m3")
    discharge_coefficient = float(payload.get("discharge_coefficient", 0.62))
    duration_s = _positive_float(payload, "duration_s")

    if "liquid_head_m" in payload:
        head_m = _positive_float(payload, "liquid_head_m")
        velocity_m_s = discharge_coefficient * math.sqrt(2 * GRAVITY * head_m)
        submodel = "gravity_driven_tank_hole"
    else:
        delta_pressure_pa = _positive_float(payload, "delta_pressure_pa")
        velocity_m_s = discharge_coefficient * math.sqrt(2 * delta_pressure_pa / density_kg_m3)
        submodel = "pipe_or_pressurized_liquid_release"

    volumetric_rate_m3_s = area_m2 * velocity_m_s
    mass_rate = volumetric_rate_m3_s * density_kg_m3
    if conservative_mode:
        mass_rate *= 1.1
    total_mass = mass_rate * duration_s

    return {
        "model_type": "liquid_release",
        "submodel": submodel,
        "release_rate_kg_s": round(mass_rate, 6),
        "volumetric_rate_m3_s": round(volumetric_rate_m3_s, 6),
        "total_mass_kg": round(total_mass, 6),
        "phase_state": "liquid",
    }


def _solve_flashing(payload: dict[str, object]) -> dict[str, object]:
    cp_liquid_j_kg_k = _positive_float(payload, "cp_liquid_j_kg_k")
    storage_temperature_k = _positive_float(payload, "storage_temperature_k")
    boiling_point_k = _positive_float(payload, "boiling_point_k")
    latent_heat_j_kg = _positive_float(payload, "latent_heat_j_kg")
    total_mass_kg = _positive_float(payload, "total_mass_kg")

    flash_fraction = max(
        0.0,
        min(1.0, cp_liquid_j_kg_k * (storage_temperature_k - boiling_point_k) / latent_heat_j_kg),
    )
    vapor_mass = total_mass_kg * flash_fraction
    rainout_mass = total_mass_kg - vapor_mass
    return {
        "model_type": "flashing",
        "flash_fraction": round(flash_fraction, 6),
        "vapor_mass_kg": round(vapor_mass, 6),
        "rainout_mass_kg": round(rainout_mass, 6),
        "phase_state": "two_phase",
    }


def _solve_pool_formation(payload: dict[str, object]) -> dict[str, object]:
    liquid_mass_kg = _positive_float(payload, "liquid_mass_kg")
    density_kg_m3 = _positive_float(payload, "density_kg_m3")
    pool_thickness_m = _positive_float(payload, "pool_thickness_m")
    containment_area_m2 = float(payload.get("containment_area_m2", 0.0))

    unconstrained_area = liquid_mass_kg / density_kg_m3 / pool_thickness_m
    if containment_area_m2 > 0:
        area = min(unconstrained_area, containment_area_m2)
        submodel = "diked_pool"
    else:
        area = unconstrained_area
        submodel = "free_spreading_pool"

    return {
        "model_type": "pool_formation",
        "submodel": submodel,
        "pool_area_m2": round(area, 6),
        "pool_diameter_m": round(math.sqrt(4 * area / math.pi), 6),
    }


def _solve_evaporation(payload: dict[str, object]) -> dict[str, object]:
    area_m2 = _positive_float(payload, "area_m2")
    latent_heat_j_kg = _positive_float(payload, "latent_heat_j_kg")

    if "heat_flux_kw_m2" in payload:
        heat_flux_kw_m2 = _positive_float(payload, "heat_flux_kw_m2")
        evaporation_rate = heat_flux_kw_m2 * 1000 * area_m2 / latent_heat_j_kg
        submodel = "heat_transfer_limited"
    else:
        mass_transfer_coefficient_m_s = _positive_float(
            payload, "mass_transfer_coefficient_m_s"
        )
        surface_concentration_kg_m3 = _positive_float(payload, "surface_concentration_kg_m3")
        evaporation_rate = (
            mass_transfer_coefficient_m_s * area_m2 * surface_concentration_kg_m3
        )
        submodel = "mass_transfer_limited"

    return {
        "model_type": "evaporation",
        "submodel": submodel,
        "evaporation_rate_kg_s": round(evaporation_rate, 6),
    }
