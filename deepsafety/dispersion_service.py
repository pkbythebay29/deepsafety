from __future__ import annotations

import math

from deepsafety.catalog import ModelInputError
from deepsafety.dispersion.neutrally_buoyant import (
    calculate_sigma_y,
    calculate_sigma_z,
    puff_dispersion_ground,
)


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


def solve_dispersion_model(model_type: str, payload: dict[str, object]) -> dict[str, object]:
    model_type = model_type.lower()
    if model_type == "gaussian_plume":
        return _solve_gaussian_plume(payload)
    if model_type == "gaussian_puff":
        return _solve_gaussian_puff(payload)
    if model_type == "dense_gas":
        return _solve_dense_gas(payload)
    raise ModelInputError(
        "Dispersion model must be one of gaussian_plume, gaussian_puff, or dense_gas."
    )


def _sigma_values(distance_m: float, stability_class: str) -> tuple[float, float]:
    return (
        calculate_sigma_y(distance_m, stability_class),
        calculate_sigma_z(distance_m, stability_class),
    )


def _solve_gaussian_plume(payload: dict[str, object]) -> dict[str, object]:
    release_rate_kg_s = _positive_float(payload, "release_rate_kg_s")
    wind_speed_m_s = _positive_float(payload, "wind_speed_m_s")
    x_m = _positive_float(payload, "x_m")
    y_m = float(payload.get("y_m", 0.0))
    z_m = float(payload.get("z_m", 0.0))
    release_height_m = float(payload.get("release_height_m", 0.0))
    stability_class = str(payload.get("stability_class", "D")).upper()
    threshold = float(payload.get("threshold_kg_m3", 0.0))

    sigma_y, sigma_z = _sigma_values(x_m, stability_class)
    reflected_term = math.exp(-0.5 * ((z_m - release_height_m) / sigma_z) ** 2) + math.exp(
        -0.5 * ((z_m + release_height_m) / sigma_z) ** 2
    )
    concentration = (
        release_rate_kg_s
        / (2 * math.pi * wind_speed_m_s * sigma_y * sigma_z)
        * math.exp(-0.5 * (y_m / sigma_y) ** 2)
        * reflected_term
    )
    threshold_distance = _distance_to_threshold_plume(
        release_rate_kg_s,
        wind_speed_m_s,
        threshold,
        release_height_m,
        stability_class,
    )
    return {
        "model_type": "gaussian_plume",
        "concentration_kg_m3": round(concentration, 8),
        "sigma_y_m": round(sigma_y, 6),
        "sigma_z_m": round(sigma_z, 6),
        "plume_width_m": round(2 * sigma_y, 6),
        "maximum_concentration_location_m": x_m if y_m == 0 and z_m == 0 else max(1.0, x_m - sigma_y),
        "distance_to_threshold_m": round(threshold_distance, 6) if threshold_distance else None,
    }


def _distance_to_threshold_plume(
    release_rate_kg_s: float,
    wind_speed_m_s: float,
    threshold_kg_m3: float,
    release_height_m: float,
    stability_class: str,
) -> float | None:
    if threshold_kg_m3 <= 0:
        return None

    last_distance = None
    for distance in range(1, 100_001, 50):
        sigma_y, sigma_z = _sigma_values(distance, stability_class)
        reflected_term = math.exp(-0.5 * ((0.0 - release_height_m) / sigma_z) ** 2) + math.exp(
            -0.5 * ((0.0 + release_height_m) / sigma_z) ** 2
        )
        concentration = (
            release_rate_kg_s
            / (2 * math.pi * wind_speed_m_s * sigma_y * sigma_z)
            * reflected_term
        )
        if concentration <= threshold_kg_m3:
            return float(distance)
        last_distance = distance
    return float(last_distance) if last_distance is not None else None


def _solve_gaussian_puff(payload: dict[str, object]) -> dict[str, object]:
    released_mass_kg = _positive_float(payload, "released_mass_kg")
    x_m = _positive_float(payload, "x_m")
    y_m = float(payload.get("y_m", 0.0))
    z_m = float(payload.get("z_m", 0.0))
    stability_class = str(payload.get("stability_class", "D")).upper()
    sigma_y, sigma_z = _sigma_values(x_m, stability_class)
    concentration = puff_dispersion_ground(
        x=x_m,
        y=y_m,
        z=z_m,
        Q=released_mass_kg,
        u=float(payload.get("wind_speed_m_s", 1.0)),
        sigma_y=sigma_y,
        sigma_z=sigma_z,
    )
    return {
        "model_type": "gaussian_puff",
        "concentration_kg_m3": round(concentration, 8),
        "sigma_y_m": round(sigma_y, 6),
        "sigma_z_m": round(sigma_z, 6),
        "plume_width_m": round(2 * sigma_y, 6),
    }


def _solve_dense_gas(payload: dict[str, object]) -> dict[str, object]:
    released_mass_kg = _positive_float(payload, "released_mass_kg")
    gas_density_kg_m3 = _positive_float(payload, "gas_density_kg_m3")
    air_density_kg_m3 = float(payload.get("air_density_kg_m3", 1.225))
    release_duration_s = _positive_float(payload, "release_duration_s")
    wind_speed_m_s = _positive_float(payload, "wind_speed_m_s")
    reduced_gravity = max(1e-6, (gas_density_kg_m3 - air_density_kg_m3) / air_density_kg_m3 * 9.81)
    cloud_volume_m3 = released_mass_kg / gas_density_kg_m3
    characteristic_radius = (cloud_volume_m3 / max(0.2, wind_speed_m_s)) ** (1 / 3) * math.sqrt(
        1 + reduced_gravity
    ) * 6
    slump_velocity = math.sqrt(reduced_gravity * max(0.5, characteristic_radius))
    cloud_length = max(characteristic_radius, slump_velocity * release_duration_s / 3)
    return {
        "model_type": "dense_gas",
        "cloud_radius_m": round(characteristic_radius, 6),
        "cloud_length_m": round(cloud_length, 6),
        "gravity_slumping_velocity_m_s": round(slump_velocity, 6),
        "maximum_concentration_location_m": round(cloud_length / 2, 6),
    }
