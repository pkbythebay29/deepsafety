from __future__ import annotations

from deepsafety.data_access import load_constants_registry, load_model_constants_registry


def get_constant_definition(name: str) -> dict[str, object]:
    constants = load_constants_registry()["constants"]
    if name not in constants:
        raise KeyError(name)
    return dict(constants[name])


def get_constant_value(name: str) -> float:
    return float(get_constant_definition(name)["value"])


def list_constants() -> dict[str, dict[str, object]]:
    return dict(load_constants_registry()["constants"])


def get_model_constant_names(model_id: str) -> tuple[str, ...]:
    return load_model_constants_registry().get(model_id, ())


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

