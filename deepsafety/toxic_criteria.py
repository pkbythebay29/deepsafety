from __future__ import annotations

from deepsafety.catalog import ModelInputError
from deepsafety.data_access import load_toxic_criteria_registry


TOXIC_CRITERIA_REGISTRY = load_toxic_criteria_registry()["criteria"]


def lookup_toxic_criteria(payload: dict[str, object]) -> dict[str, object]:
    chemical = str(payload.get("chemical", "") or "").strip().lower().replace(" ", "_")
    if not chemical:
        raise ModelInputError("Provide 'chemical' for toxic criteria lookup.")

    registry = {
        **TOXIC_CRITERIA_REGISTRY,
        **{
            str(key).strip().lower().replace(" ", "_"): value
            for key, value in dict(payload.get("criteria_overrides", {})).items()
        },
    }
    if chemical not in registry:
        raise ModelInputError(
            f"Chemical '{chemical}' is not in the starter toxic criteria registry."
        )

    entry = registry[chemical]
    units = str(entry.get("units", "ppm"))
    requested = payload.get(
        "criteria_names",
        [
            "aegl_1",
            "aegl_2",
            "aegl_3",
            "erpg_1",
            "erpg_2",
            "erpg_3",
            "idlh",
            "tlv_twa",
            "pel_twa",
            "toxic_endpoint",
        ],
    )
    if not isinstance(requested, list) or not requested:
        raise ModelInputError("Input 'criteria_names' must be a non-empty list when supplied.")

    values = {}
    for name in requested:
        criterion_name = str(name).strip().lower()
        if criterion_name not in entry:
            raise ModelInputError(
                f"Criterion '{criterion_name}' is not available for chemical '{chemical}'."
            )
        values[criterion_name] = float(entry[criterion_name])

    return {
        "model_type": "toxic_criteria_lookup",
        "chemical": chemical,
        "units": units,
        "criteria": values,
        "available_criteria": sorted(key for key in entry if key != "units"),
        "notes": [
            "The built-in registry is a starter dataset intended for API integration and extension.",
            "The packaged starter dataset is loaded from deepsafety/data/toxic_criteria_registry.json.",
            "Use criteria_overrides to inject organization-specific or updated toxic criteria values.",
        ],
    }
