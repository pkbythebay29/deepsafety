from __future__ import annotations

import math
from typing import Any

from deepsafety.catalog import ModelInputError
from deepsafety.constants import get_constant_value
from deepsafety.fire_explosion_models import solve_fire_explosion_model
from deepsafety.materials_data import get_material_flammability


def _overpressure_from_scaled_distance(z: float) -> float:
    z = max(z, 0.05)
    return 1772 / z**3 + 114 / z**2 + 10.4 / z


def evaluate_flammability_mixture(payload: dict[str, Any]) -> dict[str, Any]:
    components = payload.get("components", [])
    if not isinstance(components, list) or not components:
        raise ModelInputError("Input 'components' must be a non-empty list.")

    total_fraction = sum(float(component.get("moleFraction", 0.0)) for component in components)
    if total_fraction <= 0:
        raise ModelInputError("Total mixture mole fraction must be greater than zero.")

    lfl_sum = 0.0
    ufl_sum = 0.0
    fuel_fraction = 0.0
    contributing = 0
    for component in components:
        material = get_material_flammability(str(component.get("materialId", "")))
        mole_fraction = float(component.get("moleFraction", 0.0)) / total_fraction
        lfl = material.get("lfl")
        ufl = material.get("ufl")
        if lfl is not None and ufl is not None:
            fuel_fraction += mole_fraction
            lfl_sum += mole_fraction / float(lfl)
            ufl_sum += mole_fraction / float(ufl)
            contributing += 1

    if contributing == 0:
        return {
            "flammable": False,
            "estimatedLfl": None,
            "estimatedUfl": None,
            "notes": "No flammable components with starter LFL/UFL data were available.",
        }

    estimated_lfl = 1.0 / lfl_sum
    estimated_ufl = 1.0 / ufl_sum
    mixture_fuel_percent = fuel_fraction * 100.0
    oxygen_fraction = float(payload.get("oxygenFraction", 0.21))
    flammable = oxygen_fraction >= 0.12 and estimated_lfl <= mixture_fuel_percent <= estimated_ufl
    return {
        "flammable": flammable,
        "estimatedLfl": round(estimated_lfl, 6),
        "estimatedUfl": round(estimated_ufl, 6),
        "notes": (
            "Le Chatelier mixture approximation was used. "
            "Estimated limits are meaningful only for components with starter flammability data."
        ),
    }


def calculate_loc(payload: dict[str, Any]) -> dict[str, Any]:
    fuel_system = dict(payload.get("fuelSystem", {}))
    components = fuel_system.get("components", [])
    loc_candidates: list[float] = []
    if isinstance(components, list):
        for component in components:
            flammability = get_material_flammability(str(component.get("materialId", "")))
            if flammability.get("loc") is not None:
                loc_candidates.append(float(flammability["loc"]))
    if not loc_candidates and fuel_system.get("materialId"):
        flammability = get_material_flammability(str(fuel_system["materialId"]))
        if flammability.get("loc") is not None:
            loc_candidates.append(float(flammability["loc"]))

    loc = min(loc_candidates) if loc_candidates else 12.0
    inert_gas = str(payload.get("inertGas", "nitrogen")).strip().lower()
    if inert_gas == "carbon_dioxide":
        loc -= 0.5
    elif inert_gas == "steam":
        loc += 0.5
    operating_oxygen = float(payload.get("operatingOxygenPercent", 21.0))
    margin = loc - operating_oxygen
    return {
        "loc": round(loc, 6),
        "safe": operating_oxygen <= loc,
        "margin": round(margin, 6),
    }


def evaluate_ignition_energy(payload: dict[str, Any]) -> dict[str, Any]:
    minimum_ignition_energy = float(payload.get("minimumIgnitionEnergy", 0.0))
    available_ignition_energy = float(payload.get("availableIgnitionEnergy", 0.0))
    if minimum_ignition_energy <= 0 or available_ignition_energy < 0:
        raise ModelInputError("Ignition energies must be non-negative, and minimum ignition energy must be positive.")
    ratio = available_ignition_energy / minimum_ignition_energy
    return {
        "canIgnite": ratio >= 1.0,
        "ratio": round(ratio, 6),
    }


def calculate_tnt_equivalency(payload: dict[str, Any]) -> dict[str, Any]:
    chemical_energy = float(payload.get("chemicalEnergy", 0.0))
    efficiency = float(payload.get("efficiency", 0.0))
    if chemical_energy <= 0:
        raise ModelInputError("Input 'chemicalEnergy' must be greater than zero.")
    if not 0 <= efficiency <= 1:
        raise ModelInputError("Input 'efficiency' must be between 0 and 1.")
    return {
        "tntEquivalentMass": round(
            chemical_energy * efficiency / get_constant_value("shared.tnt_heat_of_explosion_kj_kg"),
            6,
        ),
    }


def calculate_multi_energy_blast(payload: dict[str, Any]) -> dict[str, Any]:
    tnt_equivalent_mass = float(payload.get("tntEquivalentMass", 0.0))
    distances = payload.get("distances", [])
    if tnt_equivalent_mass <= 0:
        raise ModelInputError("Input 'tntEquivalentMass' must be greater than zero.")
    if not isinstance(distances, list) or not distances:
        raise ModelInputError("Input 'distances' must be a non-empty list.")

    points = []
    for distance in distances:
        distance_value = float(distance)
        if distance_value <= 0:
            raise ModelInputError("All blast distances must be greater than zero.")
        scaled_distance = distance_value / max(tnt_equivalent_mass, 1e-9) ** (1 / 3)
        overpressure = _overpressure_from_scaled_distance(scaled_distance)
        points.append(
            {
                "distance": round(distance_value, 6),
                "overpressure": round(overpressure, 6),
                "impulse": round(overpressure * max(distance_value / 100.0, 0.1), 6),
            }
        )
    return {"points": points}


def evaluate_vce(payload: dict[str, Any]) -> dict[str, Any]:
    released_mass = float(payload.get("releasedMass", 0.0))
    vaporized_fraction = float(payload.get("vaporizedFraction", 0.0))
    if released_mass <= 0:
        raise ModelInputError("Input 'releasedMass' must be greater than zero.")
    if not 0 <= vaporized_fraction <= 1:
        raise ModelInputError("Input 'vaporizedFraction' must be between 0 and 1.")

    congestion_level = str(payload.get("congestionLevel", "medium")).strip().lower()
    congestion_factor = {"low": 0.8, "medium": 1.2, "high": 1.8}.get(congestion_level)
    if congestion_factor is None:
        raise ModelInputError("Input 'congestionLevel' must be low, medium, or high.")
    ignition_delay_s = 20.0 if bool(payload.get("delayedIgnition", False)) else 5.0
    cloud_mass = released_mass * vaporized_fraction
    solved = solve_fire_explosion_model(
        "vce",
        {
            "cloud_mass_kg": cloud_mass,
            "heat_of_combustion_kj_kg": float(payload.get("heatOfCombustion", 46_000.0)),
            "ignition_delay_s": ignition_delay_s,
            "congestion_factor": congestion_factor,
            "distance_m": 50.0,
        },
    )
    tnt_equivalent_mass = float(solved["tnt_equivalent_mass_kg"])
    overpressure_profile = calculate_multi_energy_blast(
        {"tntEquivalentMass": tnt_equivalent_mass, "distances": [25.0, 50.0, 100.0, 200.0]}
    )
    peak = max(point["overpressure"] for point in overpressure_profile["points"])
    if peak >= 70:
        severity = "severe"
    elif peak >= 35:
        severity = "major"
    elif peak >= 14:
        severity = "moderate"
    else:
        severity = "minor"
    return {
        "tntEquivalentMass": round(tnt_equivalent_mass, 6),
        "overpressureProfile": overpressure_profile,
        "qualitativeSeverity": severity,
    }


def evaluate_bleve(payload: dict[str, Any]) -> dict[str, Any]:
    inventory_mass = float(payload.get("inventoryMass", 0.0))
    liquid_temperature_k = float(payload.get("liquidTemperatureK", 0.0))
    atmospheric_boiling_point_k = float(payload.get("atmosphericBoilingPointK", 0.0))
    if inventory_mass <= 0 or liquid_temperature_k <= 0 or atmospheric_boiling_point_k <= 0:
        raise ModelInputError(
            "Inputs 'inventoryMass', 'liquidTemperatureK', and 'atmosphericBoilingPointK' must be greater than zero."
        )
    superheat_fraction = max(
        0.0,
        min(1.0, (liquid_temperature_k - atmospheric_boiling_point_k) / max(liquid_temperature_k, 1.0)),
    )
    explosive_vaporized_mass = inventory_mass * superheat_fraction
    return {
        "explosiveVaporizedMass": round(explosive_vaporized_mass, 6),
        "fireballPossible": bool(payload.get("flammable", True)),
        "toxicCloudPossible": bool(payload.get("toxic", False)),
    }
