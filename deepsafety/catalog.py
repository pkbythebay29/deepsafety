from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from deepsafety.constants import resolve_constants
from deepsafety.dispersion.neutrally_buoyant import (
    calculate_sigma_y,
    calculate_sigma_z,
    puff_dispersion_ground,
)


class ModelInputError(ValueError):
    """Raised when a model receives invalid integration inputs."""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    description: str
    unit: str | None = None
    required: bool = True
    allowed_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class CalculationModel:
    id: str
    name: str
    domain: str
    summary: str
    consequence_areas: tuple[str, ...]
    status: str
    equations: tuple[str, ...] = field(default_factory=tuple)
    constant_names: tuple[str, ...] = field(default_factory=tuple)
    supported_scenarios: tuple[str, ...] = field(default_factory=tuple)
    gis_ready: bool = False
    input_fields: tuple[FieldSpec, ...] = field(default_factory=tuple)
    output_fields: tuple[FieldSpec, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    calculator: Callable[
        [dict[str, object], dict[str, dict[str, object]]], dict[str, object]
    ] | None = None


def _require_input(payload: dict[str, object], key: str) -> object:
    if key not in payload:
        raise ModelInputError(f"Missing required input '{key}'.")
    return payload[key]


def _as_float(payload: dict[str, object], key: str) -> float:
    value = _require_input(payload, key)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ModelInputError(f"Input '{key}' must be numeric.") from exc


def _require_positive(payload: dict[str, object], key: str) -> float:
    value = _as_float(payload, key)
    if value <= 0:
        raise ModelInputError(f"Input '{key}' must be greater than zero.")
    return value


def _constant_value(
    resolved_constants: dict[str, dict[str, object]],
    name: str,
) -> float:
    if name not in resolved_constants:
        raise ModelInputError(f"Constant '{name}' is not configured for this model.")
    return float(resolved_constants[name]["value"])


def _calculate_gaussian_puff_ground(
    inputs: dict[str, object],
    resolved_constants: dict[str, dict[str, object]],
) -> dict[str, object]:
    del resolved_constants
    concentration = puff_dispersion_ground(
        x=_as_float(inputs, "x"),
        y=_as_float(inputs, "y"),
        z=_as_float(inputs, "z"),
        Q=_require_positive(inputs, "Q"),
        u=_require_positive(inputs, "u"),
        sigma_y=_require_positive(inputs, "sigma_y"),
        sigma_z=_require_positive(inputs, "sigma_z"),
    )
    return {"concentration": concentration}


def _calculate_sigma_y_pasquill_gifford(
    inputs: dict[str, object],
    resolved_constants: dict[str, dict[str, object]],
) -> dict[str, object]:
    del resolved_constants
    stability_class = str(_require_input(inputs, "stability_class")).upper()
    if stability_class not in {"A", "B", "C", "D", "E", "F"}:
        raise ModelInputError(
            "Input 'stability_class' must be one of A, B, C, D, E, or F."
        )

    sigma_y = calculate_sigma_y(
        x=_require_positive(inputs, "x"),
        stability_class=stability_class,
    )
    sigma_z = calculate_sigma_z(
        x=_require_positive(inputs, "x"),
        stability_class=stability_class,
    )
    return {"sigma_y": sigma_y, "sigma_z_screening": sigma_z}


def _calculate_flammability_limits(
    inputs: dict[str, object],
    resolved_constants: dict[str, dict[str, object]],
) -> dict[str, object]:
    absolute_zero_offset = _constant_value(
        resolved_constants, "shared.absolute_zero_offset_c"
    )
    reference_temperature = _constant_value(
        resolved_constants, "shared.reference_temperature_c"
    )
    temp_c = _as_float(inputs, "temp_c")
    lfl_20c = _require_positive(inputs, "lfl_20c")
    ufl_20c = _require_positive(inputs, "ufl_20c")

    lower_limit = lfl_20c * (absolute_zero_offset + reference_temperature) / (
        absolute_zero_offset + temp_c
    )
    upper_limit = ufl_20c * (absolute_zero_offset + temp_c) / (
        absolute_zero_offset + reference_temperature
    )
    return {
        "lower_flammability_limit": round(lower_limit, 3),
        "upper_flammability_limit": round(upper_limit, 3),
    }


def _calculate_point_source_heat_flux(
    inputs: dict[str, object],
    resolved_constants: dict[str, dict[str, object]],
) -> dict[str, object]:
    pi_value = _constant_value(resolved_constants, "shared.pi")
    radiative_fraction = _constant_value(
        resolved_constants, "fire.default_radiative_fraction"
    )
    transmissivity = _constant_value(
        resolved_constants, "fire.default_atmospheric_transmissivity"
    )
    distance_m = _require_positive(inputs, "distance_m")
    burning_rate_kg_s = _require_positive(inputs, "burning_rate_kg_s")
    heat_of_combustion_kj_kg = _require_positive(inputs, "heat_of_combustion_kj_kg")

    heat_flux_kw_m2 = (
        transmissivity
        * radiative_fraction
        * burning_rate_kg_s
        * heat_of_combustion_kj_kg
        / (4 * pi_value * distance_m**2)
    )
    return {"heat_flux_kw_m2": round(heat_flux_kw_m2, 6)}


def _calculate_point_source_heat_flux_radius(
    inputs: dict[str, object],
    resolved_constants: dict[str, dict[str, object]],
) -> dict[str, object]:
    pi_value = _constant_value(resolved_constants, "shared.pi")
    radiative_fraction = _constant_value(
        resolved_constants, "fire.default_radiative_fraction"
    )
    transmissivity = _constant_value(
        resolved_constants, "fire.default_atmospheric_transmissivity"
    )
    burning_rate_kg_s = _require_positive(inputs, "burning_rate_kg_s")
    heat_of_combustion_kj_kg = _require_positive(inputs, "heat_of_combustion_kj_kg")
    impact_threshold_kw_m2 = _require_positive(inputs, "impact_threshold_kw_m2")

    numerator = (
        transmissivity
        * radiative_fraction
        * burning_rate_kg_s
        * heat_of_combustion_kj_kg
    )
    radius_m = (numerator / (4 * pi_value * impact_threshold_kw_m2)) ** 0.5
    area_m2 = pi_value * radius_m**2
    return {
        "impact_radius_m": round(radius_m, 6),
        "impact_area_m2": round(area_m2, 6),
    }


def _calculate_gaussian_puff_screening_radius(
    inputs: dict[str, object],
    resolved_constants: dict[str, dict[str, object]],
) -> dict[str, object]:
    pi_value = _constant_value(resolved_constants, "shared.pi")
    released_mass_kg = _require_positive(inputs, "released_mass_kg")
    threshold = _require_positive(inputs, "concentration_threshold_kg_m3")
    stability_class = str(_require_input(inputs, "stability_class")).upper()
    if stability_class not in {"A", "B", "C", "D", "E", "F"}:
        raise ModelInputError(
            "Input 'stability_class' must be one of A, B, C, D, E, or F."
        )

    y = float(inputs.get("y", 0.0))
    z = float(inputs.get("z", 0.0))

    def concentration_at(distance_m: float) -> float:
        sigma_y = calculate_sigma_y(distance_m, stability_class)
        sigma_z = calculate_sigma_z(distance_m, stability_class)
        return puff_dispersion_ground(
            x=distance_m,
            y=y,
            z=z,
            Q=released_mass_kg,
            u=1.0,
            sigma_y=sigma_y,
            sigma_z=sigma_z,
        )

    minimum_distance = 1.0
    if concentration_at(minimum_distance) < threshold:
        return {
            "impact_radius_m": 0.0,
            "impact_area_m2": 0.0,
            "screening_release_mass_kg": released_mass_kg,
        }

    lower = minimum_distance
    upper = 10.0
    while concentration_at(upper) > threshold and upper < 100_000:
        upper *= 2

    for _ in range(60):
        midpoint = (lower + upper) / 2
        if concentration_at(midpoint) > threshold:
            lower = midpoint
        else:
            upper = midpoint

    radius_m = upper
    return {
        "impact_radius_m": round(radius_m, 6),
        "impact_area_m2": round(pi_value * radius_m**2, 6),
        "screening_release_mass_kg": released_mass_kg,
    }


MODEL_REGISTRY: dict[str, CalculationModel] = {
    "dispersion.gaussian_puff_ground": CalculationModel(
        id="dispersion.gaussian_puff_ground",
        name="Gaussian Puff Dispersion at Ground Level",
        domain="dispersion",
        summary="Estimate point concentration for an instantaneous ground-level release.",
        consequence_areas=("source dispersion", "neutrally buoyant releases"),
        status="implemented",
        equations=(
            "C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))",
        ),
        constant_names=("shared.pi",),
        supported_scenarios=("leak",),
        gis_ready=True,
        input_fields=(
            FieldSpec("x", "number", "Downwind distance from source.", "m"),
            FieldSpec("y", "number", "Crosswind distance from plume centerline.", "m"),
            FieldSpec("z", "number", "Vertical distance from ground reference.", "m"),
            FieldSpec("Q", "number", "Released mass or source strength.", "kg"),
            FieldSpec("u", "number", "Mean wind speed.", "m/s"),
            FieldSpec("sigma_y", "number", "Lateral dispersion coefficient.", "m"),
            FieldSpec("sigma_z", "number", "Vertical dispersion coefficient.", "m"),
        ),
        output_fields=(
            FieldSpec("concentration", "number", "Estimated concentration.", "kg/m^3"),
        ),
        notes=(
            "The GIS helper can auto-populate x, sigma_y, and sigma_z for screening runs when stability class is provided.",
        ),
        calculator=_calculate_gaussian_puff_ground,
    ),
    "dispersion.pasquill_gifford_sigma_y": CalculationModel(
        id="dispersion.pasquill_gifford_sigma_y",
        name="Pasquill-Gifford Dispersion Coefficients",
        domain="dispersion",
        summary="Estimate screening sigma_y and sigma_z values from stability class and distance.",
        consequence_areas=("atmospheric dispersion",),
        status="implemented",
        equations=(
            "sigma_y = a * x^(1 + b)",
            "sigma_z = a * x / ((1 + b * x)^n)",
        ),
        input_fields=(
            FieldSpec("x", "number", "Downwind distance.", "m"),
            FieldSpec(
                "stability_class",
                "string",
                "Pasquill stability class.",
                allowed_values=("A", "B", "C", "D", "E", "F"),
            ),
        ),
        output_fields=(
            FieldSpec("sigma_y", "number", "Lateral dispersion coefficient.", "m"),
            FieldSpec(
                "sigma_z_screening",
                "number",
                "Vertical dispersion coefficient for screening calculations.",
                "m",
            ),
        ),
        supported_scenarios=("leak",),
        gis_ready=True,
        calculator=_calculate_sigma_y_pasquill_gifford,
    ),
    "dispersion.gaussian_puff_screening_radius": CalculationModel(
        id="dispersion.gaussian_puff_screening_radius",
        name="Gaussian Puff Screening Impact Radius",
        domain="dispersion",
        summary="Estimate a screening impact radius by solving for the centerline threshold distance.",
        consequence_areas=("source dispersion", "screening impact zones"),
        status="implemented",
        equations=(
            "C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))",
            "Solve for x where C(x) = concentration_threshold using sigma_y(x) and sigma_z(x).",
        ),
        constant_names=("shared.pi",),
        supported_scenarios=("leak",),
        gis_ready=True,
        input_fields=(
            FieldSpec("released_mass_kg", "number", "Released mass used for the screening puff.", "kg"),
            FieldSpec(
                "concentration_threshold_kg_m3",
                "number",
                "Threshold concentration used to define the impact boundary.",
                "kg/m^3",
            ),
            FieldSpec(
                "stability_class",
                "string",
                "Pasquill stability class.",
                allowed_values=("A", "B", "C", "D", "E", "F"),
            ),
            FieldSpec("y", "number", "Crosswind offset used for the threshold calculation.", "m", required=False),
            FieldSpec("z", "number", "Vertical offset used for the threshold calculation.", "m", required=False),
        ),
        output_fields=(
            FieldSpec("impact_radius_m", "number", "Screening impact radius.", "m"),
            FieldSpec("impact_area_m2", "number", "Screening circular impact area.", "m^2"),
            FieldSpec(
                "screening_release_mass_kg",
                "number",
                "Release mass carried into the screening calculation.",
                "kg",
            ),
        ),
        notes=(
            "This is a screening circle derived from a centerline threshold crossing, not a full meteorological footprint.",
        ),
        calculator=_calculate_gaussian_puff_screening_radius,
    ),
    "fire.flammability_limits": CalculationModel(
        id="fire.flammability_limits",
        name="Temperature-Adjusted Flammability Limits",
        domain="fire_and_explosion",
        summary="Estimate lower and upper flammability limits as temperature changes.",
        consequence_areas=("flammability", "fire modeling"),
        status="implemented",
        equations=(
            "LFL_T = LFL_ref * (T_ref + T_abs) / (T + T_abs)",
            "UFL_T = UFL_ref * (T + T_abs) / (T_ref + T_abs)",
        ),
        constant_names=(
            "shared.absolute_zero_offset_c",
            "shared.reference_temperature_c",
        ),
        input_fields=(
            FieldSpec("temp_c", "number", "Gas temperature.", "degC"),
            FieldSpec("lfl_20c", "number", "Lower flammability limit at reference temperature.", "vol%"),
            FieldSpec("ufl_20c", "number", "Upper flammability limit at reference temperature.", "vol%"),
        ),
        output_fields=(
            FieldSpec(
                "lower_flammability_limit",
                "number",
                "Adjusted lower flammability limit.",
                "vol%",
            ),
            FieldSpec(
                "upper_flammability_limit",
                "number",
                "Adjusted upper flammability limit.",
                "vol%",
            ),
        ),
        supported_scenarios=("fire",),
        calculator=_calculate_flammability_limits,
    ),
    "fire.point_source_heat_flux": CalculationModel(
        id="fire.point_source_heat_flux",
        name="Point-Source Heat Flux",
        domain="fire_and_explosion",
        summary="Estimate radiant heat flux from a fire using a point-source screening relation.",
        consequence_areas=("fire radiation", "thermal impacts"),
        status="implemented",
        equations=(
            "q = tau_a * chi_r * m_dot * DeltaH_c / (4 * pi * r^2)",
        ),
        constant_names=(
            "shared.pi",
            "fire.default_radiative_fraction",
            "fire.default_atmospheric_transmissivity",
        ),
        supported_scenarios=("fire",),
        gis_ready=True,
        input_fields=(
            FieldSpec("distance_m", "number", "Distance between the fire and the receptor.", "m"),
            FieldSpec("burning_rate_kg_s", "number", "Mass burning rate.", "kg/s"),
            FieldSpec(
                "heat_of_combustion_kj_kg",
                "number",
                "Effective heat of combustion.",
                "kJ/kg",
            ),
        ),
        output_fields=(
            FieldSpec("heat_flux_kw_m2", "number", "Radiant heat flux at the receptor.", "kW/m^2"),
        ),
        notes=(
            "Use constants overrides to change the radiative fraction or atmospheric transmissivity without changing the endpoint contract.",
        ),
        calculator=_calculate_point_source_heat_flux,
    ),
    "fire.point_source_heat_flux_radius": CalculationModel(
        id="fire.point_source_heat_flux_radius",
        name="Point-Source Heat Flux Impact Radius",
        domain="fire_and_explosion",
        summary="Estimate a circular impact radius for a selected radiant heat threshold.",
        consequence_areas=("fire radiation", "thermal impact zones"),
        status="implemented",
        equations=(
            "r = sqrt((tau_a * chi_r * m_dot * DeltaH_c) / (4 * pi * q_threshold))",
        ),
        constant_names=(
            "shared.pi",
            "fire.default_radiative_fraction",
            "fire.default_atmospheric_transmissivity",
        ),
        supported_scenarios=("fire",),
        gis_ready=True,
        input_fields=(
            FieldSpec("burning_rate_kg_s", "number", "Mass burning rate.", "kg/s"),
            FieldSpec(
                "heat_of_combustion_kj_kg",
                "number",
                "Effective heat of combustion.",
                "kJ/kg",
            ),
            FieldSpec(
                "impact_threshold_kw_m2",
                "number",
                "Heat flux threshold used to define the impact boundary.",
                "kW/m^2",
            ),
        ),
        output_fields=(
            FieldSpec("impact_radius_m", "number", "Impact radius for the selected threshold.", "m"),
            FieldSpec("impact_area_m2", "number", "Circular impact area for the selected threshold.", "m^2"),
        ),
        calculator=_calculate_point_source_heat_flux_radius,
    ),
    "source.terms.release_rate": CalculationModel(
        id="source.terms.release_rate",
        name="Release Rate Models",
        domain="source_terms",
        summary="Placeholder for vessel, pipeline, and leak source-term models.",
        consequence_areas=("source terms", "inventory release"),
        status="planned",
        supported_scenarios=("leak",),
        notes=(
            "This family should be added next to support a full consequence workflow from release to impact.",
        ),
    ),
    "toxics.probit.exposure_response": CalculationModel(
        id="toxics.probit.exposure_response",
        name="Toxic Exposure Response",
        domain="toxics",
        summary="Placeholder for toxic dose-response and consequence metrics.",
        consequence_areas=("toxic endpoints", "human effects"),
        status="planned",
        supported_scenarios=("leak",),
    ),
    "explosion.tnt_equivalency": CalculationModel(
        id="explosion.tnt_equivalency",
        name="TNT Equivalency",
        domain="fire_and_explosion",
        summary="Placeholder for explosion energy and overpressure calculations.",
        consequence_areas=("explosions", "blast effects"),
        status="planned",
    ),
}


def list_models(include_planned: bool = True) -> list[CalculationModel]:
    models = MODEL_REGISTRY.values()
    if include_planned:
        return list(models)
    return [model for model in models if model.status == "implemented"]


def get_model(model_id: str) -> CalculationModel | None:
    return MODEL_REGISTRY.get(model_id)


def get_scenario_models(scenario_type: str) -> list[CalculationModel]:
    return [
        model
        for model in list_models(include_planned=True)
        if scenario_type in model.supported_scenarios
    ]


def run_model(
    model_id: str,
    inputs: dict[str, object],
    constant_overrides: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    model = get_model(model_id)
    if model is None:
        raise KeyError(model_id)
    if model.calculator is None or model.status != "implemented":
        raise NotImplementedError(model_id)

    try:
        resolved_constants = resolve_constants(model_id, constant_overrides)
    except ValueError as exc:
        raise ModelInputError(str(exc)) from exc

    outputs = model.calculator(inputs, resolved_constants)
    return outputs, resolved_constants
