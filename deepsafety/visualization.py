from __future__ import annotations

from deepsafety.catalog import ModelInputError
from deepsafety.dispersion_service import solve_dispersion_model
from deepsafety.gis import circle_polygon, point_feature


def build_visualization_layer(layer_type: str, payload: dict[str, object]) -> dict[str, object]:
    layer_type = layer_type.lower()
    if layer_type == "plume_map":
        return _build_plume_map(payload)
    if layer_type == "risk_contours":
        return _build_risk_contours(payload)
    if layer_type == "time_evolution":
        return _build_time_evolution(payload)
    raise ModelInputError(
        "Visualization layer must be one of plume_map, risk_contours, or time_evolution."
    )


def _build_plume_map(payload: dict[str, object]) -> dict[str, object]:
    source = payload["source"]
    grid_distances = payload.get("grid_distances_m", [50, 100, 200, 400, 800])
    grid = []
    for distance in grid_distances:
        result = solve_dispersion_model(
            "gaussian_plume",
            {
                "release_rate_kg_s": payload["release_rate_kg_s"],
                "wind_speed_m_s": payload["wind_speed_m_s"],
                "x_m": distance,
                "y_m": 0.0,
                "z_m": payload.get("z_m", 0.0),
                "release_height_m": payload.get("release_height_m", 0.0),
                "stability_class": payload.get("stability_class", "D"),
            },
        )
        grid.append({"distance_m": distance, "concentration_kg_m3": result["concentration_kg_m3"]})
    return {
        "layer_type": "plume_map",
        "source": source,
        "grid": grid,
    }


def _build_risk_contours(payload: dict[str, object]) -> dict[str, object]:
    source = payload["source"]
    scenario_type = str(payload.get("scenario_type", "fire")).lower()
    zones = payload.get("zones", [])
    features = [
        point_feature(
            source["latitude"],
            source["longitude"],
            {"role": "source", "label": source.get("label", "Source")},
        )
    ]
    for zone in zones:
        features.append(
            circle_polygon(
                source["latitude"],
                source["longitude"],
                float(zone["radius_m"]),
                {
                    "role": "risk_contour",
                    "scenario_type": scenario_type,
                    "label": zone["label"],
                    "threshold": zone["threshold"],
                    "unit": zone["unit"],
                    "radius_m": zone["radius_m"],
                },
            )
        )
    return {
        "layer_type": "risk_contours",
        "geojson": {"type": "FeatureCollection", "features": features},
    }


def _build_time_evolution(payload: dict[str, object]) -> dict[str, object]:
    source = payload["source"]
    max_radius = float(payload.get("max_radius_m", 500.0))
    steps = int(payload.get("steps", 5))
    if steps <= 0:
        raise ModelInputError("Input 'steps' must be greater than zero.")

    frames = []
    for index in range(1, steps + 1):
        radius = max_radius * index / steps
        frame = {
            "time_s": float(payload.get("frame_interval_s", 60.0)) * index,
            "radius_m": round(radius, 6),
            "feature": circle_polygon(
                source["latitude"],
                source["longitude"],
                radius,
                {
                    "role": "time_frame",
                    "frame_index": index,
                    "time_s": float(payload.get("frame_interval_s", 60.0)) * index,
                    "radius_m": round(radius, 6),
                },
            ),
        }
        frames.append(frame)

    return {
        "layer_type": "time_evolution",
        "frames": frames,
    }
