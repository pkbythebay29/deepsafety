from __future__ import annotations

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


def solve_prevention_response_model(model_type: str, payload: dict[str, object]) -> dict[str, object]:
    model_type = model_type.lower()
    if model_type == "fire_triangle_screening":
        return _solve_fire_triangle_screening(payload)
    if model_type == "autoignition_screening":
        return _solve_autoignition_screening(payload)
    if model_type == "inerting_requirement":
        return _solve_inerting_requirement(payload)
    if model_type == "ignition_energy_screening":
        return _solve_ignition_energy_screening(payload)
    if model_type == "spray_mist_screening":
        return _solve_spray_mist_screening(payload)
    if model_type == "release_prevention_screening":
        return _solve_release_prevention_screening(payload)
    if model_type == "emergency_response_planning":
        return _solve_emergency_response_planning(payload)
    raise ModelInputError(
        "Prevention/response model must be one of fire_triangle_screening, autoignition_screening, "
        "inerting_requirement, ignition_energy_screening, spray_mist_screening, "
        "release_prevention_screening, or emergency_response_planning."
    )


def _solve_fire_triangle_screening(payload: dict[str, object]) -> dict[str, object]:
    fuel_present = bool(payload.get("fuel_present", False))
    oxidizer_present = bool(payload.get("oxidizer_present", False))
    ignition_source_present = bool(payload.get("ignition_source_present", False))
    missing = []
    if not fuel_present:
        missing.append("fuel")
    if not oxidizer_present:
        missing.append("oxidizer")
    if not ignition_source_present:
        missing.append("ignition_source")
    return {
        "model_type": "fire_triangle_screening",
        "triangle_complete": fuel_present and oxidizer_present and ignition_source_present,
        "missing_elements": missing,
    }


def _solve_autoignition_screening(payload: dict[str, object]) -> dict[str, object]:
    process_temperature_c = _positive_float(payload, "process_temperature_c")
    autoignition_temperature_c = _positive_float(payload, "autoignition_temperature_c")
    safety_margin_c = autoignition_temperature_c - process_temperature_c
    return {
        "model_type": "autoignition_screening",
        "safety_margin_c": round(safety_margin_c, 6),
        "autoignition_risk": "high" if safety_margin_c <= 0 else "elevated" if safety_margin_c < 50 else "screened_low",
    }


def _solve_inerting_requirement(payload: dict[str, object]) -> dict[str, object]:
    initial_oxygen_fraction = _positive_float(payload, "initial_oxygen_fraction")
    target_oxygen_fraction = _positive_float(payload, "target_oxygen_fraction")
    protected_volume_m3 = _positive_float(payload, "protected_volume_m3")
    inert_gas_purity_fraction = float(payload.get("inert_gas_purity_fraction", 0.99))
    if target_oxygen_fraction >= initial_oxygen_fraction:
        raise ModelInputError("Input 'target_oxygen_fraction' must be lower than 'initial_oxygen_fraction'.")
    if not 0 < inert_gas_purity_fraction <= 1:
        raise ModelInputError("Input 'inert_gas_purity_fraction' must be between 0 and 1.")

    oxygen_removed = initial_oxygen_fraction - target_oxygen_fraction
    inert_gas_required_m3 = protected_volume_m3 * oxygen_removed / inert_gas_purity_fraction
    return {
        "model_type": "inerting_requirement",
        "oxygen_removed_fraction": round(oxygen_removed, 6),
        "inert_gas_required_m3": round(inert_gas_required_m3, 6),
    }


def _solve_ignition_energy_screening(payload: dict[str, object]) -> dict[str, object]:
    source_energy_mj = _positive_float(payload, "source_energy_mj")
    minimum_ignition_energy_mj = _positive_float(payload, "minimum_ignition_energy_mj")
    ratio = source_energy_mj / minimum_ignition_energy_mj
    return {
        "model_type": "ignition_energy_screening",
        "energy_ratio": round(ratio, 6),
        "ignition_likelihood": "credible" if ratio >= 1 else "screened_low",
    }


def _solve_spray_mist_screening(payload: dict[str, object]) -> dict[str, object]:
    droplet_size_microns = _positive_float(payload, "droplet_size_microns")
    flash_point_c = _positive_float(payload, "flash_point_c")
    liquid_temperature_c = _positive_float(payload, "liquid_temperature_c")
    spray_pressure_bar = _positive_float(payload, "spray_pressure_bar")
    atomization_factor = spray_pressure_bar / max(droplet_size_microns, 1.0)
    mist_enhancement_factor = atomization_factor * max(liquid_temperature_c / max(flash_point_c, 1.0), 0.1)
    return {
        "model_type": "spray_mist_screening",
        "atomization_factor": round(atomization_factor, 6),
        "mist_enhancement_factor": round(mist_enhancement_factor, 6),
        "mist_fire_risk": "elevated" if mist_enhancement_factor >= 1 else "screened_low",
    }


def _solve_release_prevention_screening(payload: dict[str, object]) -> dict[str, object]:
    barrier_count = _positive_float(payload, "barrier_count")
    detection_time_s = _positive_float(payload, "detection_time_s")
    isolation_time_s = _positive_float(payload, "isolation_time_s")
    inspection_interval_days = _positive_float(payload, "inspection_interval_days")
    shutdown_success_probability = float(payload.get("shutdown_success_probability", 0.9))
    if not 0 <= shutdown_success_probability <= 1:
        raise ModelInputError("Input 'shutdown_success_probability' must be between 0 and 1.")

    protection_score = barrier_count * shutdown_success_probability / (1 + detection_time_s / 60 + isolation_time_s / 60)
    inspection_factor = 30.0 / inspection_interval_days
    return {
        "model_type": "release_prevention_screening",
        "prevention_score": round(protection_score * inspection_factor, 6),
        "barrier_health_factor": round(inspection_factor, 6),
        "screening_assessment": "strong" if protection_score * inspection_factor >= 1 else "needs_attention",
    }


def _solve_emergency_response_planning(payload: dict[str, object]) -> dict[str, object]:
    population_exposed = _positive_float(payload, "population_exposed")
    response_team_time_s = _positive_float(payload, "response_team_time_s")
    shelter_in_place_time_s = _positive_float(payload, "shelter_in_place_time_s")
    evacuation_time_s = _positive_float(payload, "evacuation_time_s")
    release_duration_s = _positive_float(payload, "release_duration_s")

    preferred_action = "shelter_in_place" if shelter_in_place_time_s <= evacuation_time_s else "evacuate"
    urgency_score = population_exposed * release_duration_s / max(response_team_time_s, 1.0)
    return {
        "model_type": "emergency_response_planning",
        "preferred_action": preferred_action,
        "urgency_score": round(urgency_score, 6),
        "response_window_s": round(min(shelter_in_place_time_s, evacuation_time_s), 6),
    }
