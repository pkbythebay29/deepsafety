from __future__ import annotations

import math


EARTH_RADIUS_M = 6_371_000.0


def haversine_distance_m(
    source_lat: float,
    source_lon: float,
    target_lat: float,
    target_lon: float,
) -> float:
    lat1 = math.radians(source_lat)
    lon1 = math.radians(source_lon)
    lat2 = math.radians(target_lat)
    lon2 = math.radians(target_lon)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def point_feature(
    latitude: float,
    longitude: float,
    properties: dict[str, object],
) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": properties,
    }


def circle_polygon(
    latitude: float,
    longitude: float,
    radius_m: float,
    properties: dict[str, object],
    segments: int = 64,
) -> dict[str, object]:
    coordinates: list[list[float]] = []
    angular_distance = radius_m / EARTH_RADIUS_M
    lat_rad = math.radians(latitude)
    lon_rad = math.radians(longitude)

    for step in range(segments + 1):
        bearing = 2 * math.pi * step / segments
        target_lat = math.asin(
            math.sin(lat_rad) * math.cos(angular_distance)
            + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing)
        )
        target_lon = lon_rad + math.atan2(
            math.sin(bearing) * math.sin(angular_distance) * math.cos(lat_rad),
            math.cos(angular_distance) - math.sin(lat_rad) * math.sin(target_lat),
        )
        coordinates.append([math.degrees(target_lon), math.degrees(target_lat)])

    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [coordinates]},
        "properties": properties,
    }
