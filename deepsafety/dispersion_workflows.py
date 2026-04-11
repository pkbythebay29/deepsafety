from __future__ import annotations

import math
import uuid
from typing import Any

from deepsafety.catalog import ModelInputError
from deepsafety.dispersion_service import solve_dispersion_model


DISPERSION_RESULTS: dict[str, dict[str, Any]] = {}


def _grid_points(grid: dict[str, Any]) -> list[tuple[float, float, float]]:
    x_min = float(grid.get("xMin", 0.0))
    x_max = float(grid.get("xMax", x_min))
    y_min = float(grid.get("yMin", 0.0))
    y_max = float(grid.get("yMax", y_min))
    z = float(grid.get("z", 0.0))
    dx = max(float(grid.get("dx", max(x_max - x_min, 1.0) or 1.0)), 1.0)
    dy = max(float(grid.get("dy", max(y_max - y_min, 1.0) or 1.0)), 1.0)
    points: list[tuple[float, float, float]] = []
    x = x_min
    while x <= x_max + 1e-9:
        y = y_min
        while y <= y_max + 1e-9:
            points.append((x, y, z))
            y += dy
        x += dx
    return points


def _store_dispersion_result(result: dict[str, Any]) -> dict[str, Any]:
    result_id = str(uuid.uuid4())
    stored = {"resultId": result_id, **result}
    DISPERSION_RESULTS[result_id] = stored
    return stored


def run_gaussian_plume(payload: dict[str, Any]) -> dict[str, Any]:
    points = []
    max_point = None
    max_concentration = -1.0
    for x, y, z in _grid_points(dict(payload.get("receptorGrid", {}))):
        solved = solve_dispersion_model(
            "gaussian_plume",
            {
                "release_rate_kg_s": float(payload["releaseRate"]),
                "release_height_m": float(payload.get("releaseHeight", 0.0)),
                "wind_speed_m_s": float(payload["windSpeed"]),
                "stability_class": str(payload["stabilityClass"]),
                "x_m": max(x, 1.0),
                "y_m": y,
                "z_m": z,
            },
        )
        concentration = float(solved["concentration_kg_m3"])
        point = {"x": x, "y": y, "z": z, "time": None, "concentration": concentration}
        points.append(point)
        if concentration > max_concentration:
            max_concentration = concentration
            max_point = {"x": x, "y": y, "z": z}
    return _store_dispersion_result(
        {
            "concentrations": points,
            "maxConcentration": round(max_concentration, 8),
            "maxConcentrationLocation": max_point,
        }
    )


def run_gaussian_puff(payload: dict[str, Any]) -> dict[str, Any]:
    points = []
    max_point = None
    max_concentration = -1.0
    for x, y, z in _grid_points(dict(payload.get("receptorGrid", {}))):
        solved = solve_dispersion_model(
            "gaussian_puff",
            {
                "released_mass_kg": float(payload["releasedMass"]),
                "wind_speed_m_s": float(payload["windSpeed"]),
                "stability_class": str(payload["stabilityClass"]),
                "x_m": max(x, 1.0),
                "y_m": y,
                "z_m": z,
            },
        )
        concentration = float(solved["concentration_kg_m3"])
        point = {"x": x, "y": y, "z": z, "time": 0.0, "concentration": concentration}
        points.append(point)
        if concentration > max_concentration:
            max_concentration = concentration
            max_point = {"x": x, "y": y, "z": z}
    return _store_dispersion_result(
        {
            "concentrations": points,
            "maxConcentration": round(max_concentration, 8),
            "maxConcentrationLocation": max_point,
        }
    )


def run_dense_gas(payload: dict[str, Any]) -> dict[str, Any]:
    released_mass = float(payload.get("releasedMass") or payload.get("releaseRate") or 1.0)
    solved = solve_dispersion_model(
        "dense_gas",
        {
            "released_mass_kg": released_mass,
            "gas_density_kg_m3": float(payload.get("gasDensityKgM3", 2.0)),
            "release_duration_s": float(payload.get("releaseDurationS", 120.0)),
            "wind_speed_m_s": float(payload["windSpeed"]),
        },
    )
    radius = float(solved["cloud_radius_m"])
    receptor_grid = dict(payload.get("receptorGrid", {}))
    y_min = float(receptor_grid.get("yMin", -radius))
    y_max = float(receptor_grid.get("yMax", radius))
    x_max = float(receptor_grid.get("xMax", float(solved["cloud_length_m"])))
    concentrations = []
    max_concentration = 0.0
    max_location = {"x": 0.0, "y": 0.0, "z": float(receptor_grid.get("z", 0.0))}
    for x, y, z in _grid_points(
        {
            "xMin": float(receptor_grid.get("xMin", 0.0)),
            "xMax": x_max,
            "yMin": y_min,
            "yMax": y_max,
            "z": float(receptor_grid.get("z", 0.0)),
            "dx": float(receptor_grid.get("dx", max(x_max / 10, 1.0))),
            "dy": float(receptor_grid.get("dy", max((y_max - y_min) / 10, 1.0))),
        }
    ):
        radial_decay = math.exp(-(abs(y) / max(radius, 1.0)) ** 2)
        downwind_decay = math.exp(-(x / max(float(solved["cloud_length_m"]), 1.0)) ** 2)
        concentration = released_mass / max(radius * float(solved["cloud_length_m"]), 1.0) * radial_decay * downwind_decay
        concentrations.append({"x": x, "y": y, "z": z, "time": None, "concentration": round(concentration, 8)})
        if concentration > max_concentration:
            max_concentration = concentration
            max_location = {"x": x, "y": y, "z": z}
    return _store_dispersion_result(
        {
            "concentrations": concentrations,
            "maxConcentration": round(max_concentration, 8),
            "maxConcentrationLocation": max_location,
        }
    )


def get_isopleth(payload: dict[str, Any]) -> dict[str, Any]:
    result_id = str(payload.get("dispersionResultId", ""))
    threshold = float(payload.get("threshold", 0.0))
    if result_id not in DISPERSION_RESULTS:
        raise ModelInputError("Dispersion result was not found.")
    if threshold <= 0:
        raise ModelInputError("Input 'threshold' must be greater than zero.")
    result = DISPERSION_RESULTS[result_id]
    exceeding = [item for item in result["concentrations"] if float(item["concentration"]) >= threshold]
    if not exceeding:
        return {"boundary": [], "maxDistance": 0.0, "maxWidth": 0.0, "area": 0.0}
    boundary = [{"x": item["x"], "y": item["y"]} for item in exceeding]
    max_distance = max(float(item["x"]) for item in exceeding)
    min_y = min(float(item["y"]) for item in exceeding)
    max_y = max(float(item["y"]) for item in exceeding)
    width = max_y - min_y
    area = max_distance * max(width, 1.0)
    return {
        "boundary": boundary,
        "maxDistance": round(max_distance, 6),
        "maxWidth": round(width, 6),
        "area": round(area, 6),
    }


def evaluate_toxic_endpoints(payload: dict[str, Any]) -> dict[str, Any]:
    result_id = str(payload.get("dispersionResultId", ""))
    criteria = payload.get("criteria", [])
    if result_id not in DISPERSION_RESULTS:
        raise ModelInputError("Dispersion result was not found.")
    result = DISPERSION_RESULTS[result_id]
    response = []
    for criterion in criteria:
        value = float(criterion["value"])
        exceeded = [item for item in result["concentrations"] if float(item["concentration"]) >= value]
        response.append(
            {
                "name": str(criterion["name"]),
                "maxDistance": round(max((float(item["x"]) for item in exceeded), default=0.0), 6),
                "exceededArea": round(float(len(exceeded)), 6),
            }
        )
    return {"criteriaResults": response}


def evaluate_release_mitigation(payload: dict[str, Any]) -> dict[str, Any]:
    release_rate = float(payload.get("releaseRate", 0.0))
    mitigation = float(payload.get("mitigationFactor", 0.0))
    wind_speed = float(payload.get("windSpeed", 3.0))
    if release_rate <= 0:
        raise ModelInputError("Input 'releaseRate' must be greater than zero.")
    if not 0 <= mitigation <= 1:
        raise ModelInputError("Input 'mitigationFactor' must be between 0 and 1.")
    revised = {
        "releaseRate": round(release_rate * (1 - mitigation), 6),
        "windSpeed": wind_speed,
        "mitigationFactor": mitigation,
    }
    return {
        "qualitativeImpact": "significant_reduction" if mitigation >= 0.5 else "moderate_reduction",
        "revisedScenario": revised,
    }
