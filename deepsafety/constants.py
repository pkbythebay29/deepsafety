from __future__ import annotations

from deepsafety.data_access import load_constants_registry


DEFAULT_CONSTANTS: dict[str, dict[str, object]] = load_constants_registry()["constants"]


MODEL_CONSTANTS: dict[str, tuple[str, ...]] = {
    "dispersion.gaussian_puff_ground": ("shared.pi",),
    "dispersion.gaussian_puff_screening_radius": ("shared.pi",),
    "fire.flammability_limits": (
        "shared.absolute_zero_offset_c",
        "shared.reference_temperature_c",
    ),
    "fire.point_source_heat_flux": (
        "shared.pi",
        "fire.default_radiative_fraction",
        "fire.default_atmospheric_transmissivity",
    ),
    "fire.point_source_heat_flux_radius": (
        "shared.pi",
        "fire.default_radiative_fraction",
        "fire.default_atmospheric_transmissivity",
    ),
}


def get_constant_definition(name: str) -> dict[str, object]:
    if name not in DEFAULT_CONSTANTS:
        raise KeyError(name)
    return DEFAULT_CONSTANTS[name]


def get_constant_value(name: str) -> float:
    return float(get_constant_definition(name)["value"])


def list_constants() -> dict[str, dict[str, object]]:
    return DEFAULT_CONSTANTS


def get_model_constant_names(model_id: str) -> tuple[str, ...]:
    return MODEL_CONSTANTS.get(model_id, ())


def resolve_constants(
    model_id: str,
    overrides: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    resolved: dict[str, dict[str, object]] = {}
    overrides = overrides or {}

    for name in get_model_constant_names(model_id):
        definition = get_constant_definition(name)
        value = overrides.get(name, definition["value"])
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Constant '{name}' must be numeric.") from exc

        resolved[name] = {
            "value": numeric_value,
            "unit": definition["unit"],
            "description": definition["description"],
            "physical_meaning": definition.get("physical_meaning"),
            "source": "override" if name in overrides else str(definition.get("source", "default")),
        }

    return resolved
