from __future__ import annotations

from deepsafety.catalog import ModelInputError
from deepsafety.data_access import load_materials_registry


def _materials() -> list[dict[str, object]]:
    return list(load_materials_registry()["materials"])


def list_materials(query: str | None = None, page: int = 1, page_size: int = 20) -> dict[str, object]:
    filtered = _materials()
    if query:
        normalized = query.strip().lower()
        filtered = [
            material
            for material in filtered
            if normalized in str(material["id"]).lower()
            or normalized in str(material["name"]).lower()
            or normalized in str(material.get("casNumber", "")).lower()
        ]
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": filtered[start:end],
        "page": page,
        "pageSize": page_size,
        "total": len(filtered),
    }


def get_material(material_id: str) -> dict[str, object]:
    normalized = material_id.strip().lower()
    for material in _materials():
        if str(material["id"]).lower() == normalized:
            return material
    raise ModelInputError(f"Material '{material_id}' was not found in the starter registry.")


def get_material_toxicity(material_id: str) -> dict[str, object]:
    material = get_material(material_id)
    toxicity = dict(material.get("toxicity", {}))
    toxicity.setdefault("materialId", material["id"])
    return toxicity


def get_material_flammability(material_id: str) -> dict[str, object]:
    material = get_material(material_id)
    flammability = dict(material.get("flammability", {}))
    flammability.setdefault("materialId", material["id"])
    return flammability


def get_material_reactivity(material_id: str) -> dict[str, object]:
    material = get_material(material_id)
    reactivity = dict(material.get("reactivity", {}))
    reactivity.setdefault("materialId", material["id"])
    return reactivity
