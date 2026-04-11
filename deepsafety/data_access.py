from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


def _read_json(filename: str) -> dict[str, Any]:
    data_path = files("deepsafety").joinpath("data", filename)
    return json.loads(data_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def load_materials_registry() -> dict[str, Any]:
    return _read_json("materials_registry.json")


@lru_cache(maxsize=None)
def load_toxic_criteria_registry() -> dict[str, Any]:
    return _read_json("toxic_criteria_registry.json")


@lru_cache(maxsize=None)
def load_constants_registry() -> dict[str, Any]:
    return _read_json("constants_registry.json")
