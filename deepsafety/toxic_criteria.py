from __future__ import annotations

from deepsafety.catalog import ModelInputError


TOXIC_CRITERIA_REGISTRY = {
    "chlorine": {
        "units": "ppm",
        "aegl_1": 0.5,
        "aegl_2": 2.8,
        "aegl_3": 50.0,
        "erpg_1": 1.0,
        "erpg_2": 3.0,
        "erpg_3": 20.0,
        "idlh": 10.0,
        "tlv_twa": 0.5,
        "pel_twa": 1.0,
        "toxic_endpoint": 3.0,
    },
    "ammonia": {
        "units": "ppm",
        "aegl_1": 30.0,
        "aegl_2": 160.0,
        "aegl_3": 1100.0,
        "erpg_1": 25.0,
        "erpg_2": 150.0,
        "erpg_3": 750.0,
        "idlh": 300.0,
        "tlv_twa": 25.0,
        "pel_twa": 50.0,
        "toxic_endpoint": 150.0,
    },
    "hydrogen_sulfide": {
        "units": "ppm",
        "aegl_1": 0.75,
        "aegl_2": 41.0,
        "aegl_3": 76.0,
        "erpg_1": 0.1,
        "erpg_2": 30.0,
        "erpg_3": 100.0,
        "idlh": 100.0,
        "tlv_twa": 1.0,
        "pel_twa": 20.0,
        "toxic_endpoint": 30.0,
    },
    "sulfur_dioxide": {
        "units": "ppm",
        "aegl_1": 0.2,
        "aegl_2": 0.75,
        "aegl_3": 30.0,
        "erpg_1": 0.3,
        "erpg_2": 3.0,
        "erpg_3": 15.0,
        "idlh": 100.0,
        "tlv_twa": 0.25,
        "pel_twa": 5.0,
        "toxic_endpoint": 3.0,
    },
}


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
            "Use criteria_overrides to inject organization-specific or updated toxic criteria values.",
        ],
    }
