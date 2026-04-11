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


def _optional_float(payload: dict[str, object], key: str, default: float) -> float:
    if key not in payload:
        return default
    try:
        return float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"Input '{key}' must be numeric.") from exc


def _area_from_payload(payload: dict[str, object], preferred_key: str | None = None) -> float:
    if preferred_key and preferred_key in payload:
        return _positive_float(payload, preferred_key)
    if "area_m2" in payload:
        return _positive_float(payload, "area_m2")
    if "hole_area_m2" in payload:
        return _positive_float(payload, "hole_area_m2")
    if "orifice_area_m2" in payload:
        return _positive_float(payload, "orifice_area_m2")
    if "relief_area_m2" in payload:
        return _positive_float(payload, "relief_area_m2")
    diameter_key = preferred_key.replace("_area_m2", "_diameter_m") if preferred_key else None
    if diameter_key and diameter_key in payload:
        diameter = _positive_float(payload, diameter_key)
        return math.pi * diameter**2 / 4
    if "diameter_m" in payload:
        diameter = _positive_float(payload, "diameter_m")
        return math.pi * diameter**2 / 4
    if "hole_diameter_m" in payload:
        diameter = _positive_float(payload, "hole_diameter_m")
        return math.pi * diameter**2 / 4
    if "pipe_diameter_m" in payload:
        diameter = _positive_float(payload, "pipe_diameter_m")
        return math.pi * diameter**2 / 4
    raise ModelInputError("Provide an area or diameter for the discharge geometry.")


def _inventory_mass_limit(payload: dict[str, object], requested_mass_kg: float) -> float:
    inventory_mass_kg = _optional_float(payload, "inventory_mass_kg", requested_mass_kg)
    return min(requested_mass_kg, inventory_mass_kg)


def _specific_gas_constant(molecular_weight_kg_kmol: float) -> float:
    return UNIVERSAL_GAS_CONSTANT / (molecular_weight_kg_kmol / 1000.0)


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


def _pipe_friction_factor(payload: dict[str, object]) -> float:
    reynolds_number = _optional_float(payload, "reynolds_number", 100_000.0)
    relative_roughness = _optional_float(payload, "relative_roughness", 0.00015)
    if reynolds_number <= 2000:
        return 64.0 / reynolds_number
    return 0.25 / (
        math.log10(relative_roughness / 3.7 + 5.74 / reynolds_number**0.9) ** 2
    )


def _solve_gas_release(payload: dict[str, object], conservative_mode: bool) -> dict[str, object]:
    subtype = str(payload.get("source_subtype", payload.get("discharge_geometry", "hole"))).lower()
    duration_s = _positive_float(payload, "duration_s")
    upstream_pressure_pa = _positive_float(payload, "upstream_pressure_pa")
    downstream_pressure_pa = _positive_float(payload, "downstream_pressure_pa")
    temperature_k = _positive_float(payload, "temperature_k")
    heat_capacity_ratio = _positive_float(payload, "heat_capacity_ratio")
    molecular_weight_kg_kmol = _positive_float(payload, "molecular_weight_kg_kmol")
    discharge_coefficient = _optional_float(payload, "discharge_coefficient", 0.62)
    compressibility = _optional_float(payload, "compressibility", 1.0)
    specific_gas_constant = _specific_gas_constant(molecular_weight_kg_kmol)

    if subtype in {"pipe", "pipeline", "pipe_rupture"}:
        area_m2 = _area_from_payload(payload, "pipe_area_m2")
        discharge_geometry = "pipe"
    elif subtype in {"relief", "relief_discharge"}:
        area_m2 = _area_from_payload(payload, "relief_area_m2")
        discharge_geometry = "relief_discharge"
    else:
        area_m2 = _area_from_payload(payload, "hole_area_m2")
        discharge_geometry = "hole"

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

    inventory_mass_kg = _optional_float(payload, "inventory_mass_kg", mass_rate * duration_s)
    if "vessel_volume_m3" in payload:
        vessel_volume_m3 = _positive_float(payload, "vessel_volume_m3")
        initial_density = upstream_pressure_pa / (compressibility * specific_gas_constant * temperature_k)
        final_pressure_pa = max(downstream_pressure_pa, _optional_float(payload, "final_pressure_pa", downstream_pressure_pa))
        final_density = final_pressure_pa / (compressibility * specific_gas_constant * temperature_k)
        inventory_mass_kg = min(
            inventory_mass_kg,
            max(0.0, (initial_density - final_density) * vessel_volume_m3),
        )
        discharge_geometry = "vessel_blowdown"

    if discharge_geometry == "pipe":
        pipe_length_m = _optional_float(payload, "pipe_length_m", 0.0)
        pipe_diameter_m = _optional_float(payload, "pipe_diameter_m", 0.0)
        if pipe_length_m > 0 and pipe_diameter_m > 0:
            friction_factor = _pipe_friction_factor(payload)
            friction_multiplier = max(
                0.15,
                1.0 / math.sqrt(1.0 + friction_factor * pipe_length_m / pipe_diameter_m),
            )
            mass_rate *= friction_multiplier

    if discharge_geometry == "relief_discharge":
        relieving_factor = _optional_float(payload, "relieving_factor", 1.0)
        mass_rate *= relieving_factor

    if conservative_mode:
        mass_rate *= 1.15

    total_mass_kg = _inventory_mass_limit(payload, mass_rate * duration_s)
    average_mass_rate = total_mass_kg / duration_s
    gas_density_kg_m3 = upstream_pressure_pa / (compressibility * specific_gas_constant * temperature_k)
    volumetric_rate_m3_s = average_mass_rate / gas_density_kg_m3
    return {
        "model_type": "gas_release",
        "submodel": "choked_flow" if choked else "non_choked_compressible_flow",
        "source_subtype": discharge_geometry,
        "release_rate_kg_s": round(mass_rate, 6),
        "average_release_rate_kg_s": round(average_mass_rate, 6),
        "volumetric_rate_m3_s": round(volumetric_rate_m3_s, 6),
        "total_mass_kg": round(total_mass_kg, 6),
        "phase_state": "gas",
        "critical_pressure_ratio": round(critical_ratio, 6),
        "gas_density_kg_m3": round(gas_density_kg_m3, 6),
    }


def _solve_liquid_release(payload: dict[str, object], conservative_mode: bool) -> dict[str, object]:
    subtype = str(payload.get("source_subtype", "hole_in_tank")).lower()
    density_kg_m3 = _positive_float(payload, "density_kg_m3")
    discharge_coefficient = _optional_float(payload, "discharge_coefficient", 0.62)
    duration_s = _positive_float(payload, "duration_s")

    if subtype in {"hole_in_tank", "tank_leak", "gravity_driven"}:
        area_m2 = _area_from_payload(payload, "hole_area_m2")
        head_m = _positive_float(payload, "liquid_head_m")
        velocity_m_s = discharge_coefficient * math.sqrt(2 * GRAVITY * head_m)
        submodel = "gravity_driven_tank_hole"
    else:
        area_m2 = _area_from_payload(payload, "pipe_area_m2")
        delta_pressure_pa = _positive_float(payload, "delta_pressure_pa")
        velocity_m_s = math.sqrt(2 * delta_pressure_pa / density_kg_m3)
        pipe_length_m = _optional_float(payload, "pipe_length_m", 0.0)
        pipe_diameter_m = _optional_float(payload, "pipe_diameter_m", 0.0)
        if pipe_length_m > 0 and pipe_diameter_m > 0:
            friction_factor = _pipe_friction_factor(payload)
            velocity_m_s *= max(
                0.15,
                1.0 / math.sqrt(1.0 + friction_factor * pipe_length_m / pipe_diameter_m),
            )
        velocity_m_s *= discharge_coefficient
        submodel = "pipe_flow"

    volumetric_rate_m3_s = area_m2 * velocity_m_s
    mass_rate = volumetric_rate_m3_s * density_kg_m3
    if conservative_mode:
        mass_rate *= 1.1
    total_mass_kg = _inventory_mass_limit(payload, mass_rate * duration_s)
    average_mass_rate = total_mass_kg / duration_s

    return {
        "model_type": "liquid_release",
        "submodel": submodel,
        "release_rate_kg_s": round(mass_rate, 6),
        "average_release_rate_kg_s": round(average_mass_rate, 6),
        "volumetric_rate_m3_s": round(volumetric_rate_m3_s, 6),
        "total_mass_kg": round(total_mass_kg, 6),
        "phase_state": "liquid",
        "exit_velocity_m_s": round(velocity_m_s, 6),
    }


def _solve_flashing(payload: dict[str, object]) -> dict[str, object]:
    cp_liquid_j_kg_k = _positive_float(payload, "cp_liquid_j_kg_k")
    storage_temperature_k = _positive_float(payload, "storage_temperature_k")
    boiling_point_k = _positive_float(payload, "boiling_point_k")
    latent_heat_j_kg = _positive_float(payload, "latent_heat_j_kg")
    total_mass_kg = _positive_float(payload, "total_mass_kg")
    entrainment_fraction = _optional_float(payload, "entrainment_fraction", 0.0)

    flash_fraction = max(
        0.0,
        min(1.0, cp_liquid_j_kg_k * (storage_temperature_k - boiling_point_k) / latent_heat_j_kg),
    )
    aerosol_fraction = min(1.0, max(0.0, entrainment_fraction))
    vapor_mass = total_mass_kg * flash_fraction
    entrained_liquid_mass = (total_mass_kg - vapor_mass) * aerosol_fraction
    rainout_mass = total_mass_kg - vapor_mass - entrained_liquid_mass
    return {
        "model_type": "flashing",
        "flash_fraction": round(flash_fraction, 6),
        "vapor_mass_kg": round(vapor_mass, 6),
        "entrained_liquid_mass_kg": round(entrained_liquid_mass, 6),
        "rainout_mass_kg": round(max(rainout_mass, 0.0), 6),
        "phase_state": "two_phase",
    }


def _solve_pool_formation(payload: dict[str, object]) -> dict[str, object]:
    liquid_mass_kg = _positive_float(payload, "liquid_mass_kg")
    density_kg_m3 = _positive_float(payload, "density_kg_m3")
    pool_thickness_m = _positive_float(payload, "pool_thickness_m")
    containment_area_m2 = _optional_float(payload, "containment_area_m2", 0.0)
    spreading_factor = _optional_float(payload, "spreading_factor", 1.0)

    unconstrained_area = liquid_mass_kg / density_kg_m3 / pool_thickness_m * spreading_factor
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
        "contained_fraction": round(area / unconstrained_area if unconstrained_area > 0 else 0.0, 6),
    }


def _solve_evaporation(payload: dict[str, object]) -> dict[str, object]:
    area_m2 = _positive_float(payload, "area_m2")
    latent_heat_j_kg = _positive_float(payload, "latent_heat_j_kg")

    if "heat_flux_kw_m2" in payload:
        heat_flux_kw_m2 = _positive_float(payload, "heat_flux_kw_m2")
        evaporation_rate = heat_flux_kw_m2 * 1000 * area_m2 / latent_heat_j_kg
        submodel = "heat_transfer_limited"
    elif "wall_heat_input_kw" in payload:
        wall_heat_input_kw = _positive_float(payload, "wall_heat_input_kw")
        evaporation_rate = wall_heat_input_kw * 1000 / latent_heat_j_kg
        submodel = "boiling_heat_input_limited"
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
