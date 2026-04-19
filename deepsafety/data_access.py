from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from threading import Lock
from typing import Any


MODEL_CONSTANTS_SEED: dict[str, tuple[str, ...]] = {
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


_DB_LOCK = Lock()


def _read_json(filename: str) -> dict[str, Any]:
    data_path = files("deepsafety").joinpath("data", filename)
    return json.loads(data_path.read_text(encoding="utf-8"))


def _database_path() -> str:
    configured = os.environ.get("DEEPSAFETY_DB_PATH")
    if configured:
        return configured
    return str(Path(tempfile.gettempdir()) / "deepsafety.sqlite3")


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    database_path = _database_path()
    connection = sqlite3.connect(database_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@lru_cache(maxsize=1)
def get_connection() -> sqlite3.Connection:
    connection = _connect()
    initialize_database(connection)
    return connection


def initialize_database(connection: sqlite3.Connection | None = None) -> None:
    conn = connection or get_connection()
    with _DB_LOCK:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS constants (
                name TEXT PRIMARY KEY,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                description TEXT NOT NULL,
                physical_meaning TEXT,
                source TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_constants (
                model_id TEXT NOT NULL,
                constant_name TEXT NOT NULL,
                PRIMARY KEY (model_id, constant_name),
                FOREIGN KEY (constant_name) REFERENCES constants(name) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS idempotency_keys (
                scope TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                resource_id TEXT,
                response_json TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                PRIMARY KEY (scope, idempotency_key)
            );

            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                model_profile_json TEXT NOT NULL,
                scenario_mode TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS scenario_versions (
                scenario_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                PRIMARY KEY (scenario_id, version),
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                analysis_type TEXT NOT NULL,
                status TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                status TEXT NOT NULL,
                sampling_json TEXT NOT NULL,
                outputs_of_interest_json TEXT NOT NULL,
                correlations_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                retain_samples INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS simulation_samples (
                simulation_id TEXT NOT NULL,
                sample_index INTEGER NOT NULL,
                inputs_json TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, sample_index),
                FOREIGN KEY (simulation_id) REFERENCES simulations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS simulation_sensitivity (
                simulation_id TEXT PRIMARY KEY,
                result_json TEXT NOT NULL,
                FOREIGN KEY (simulation_id) REFERENCES simulations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS heatmaps (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                source_json TEXT NOT NULL,
                heatmap_type TEXT NOT NULL,
                status TEXT NOT NULL,
                metric TEXT NOT NULL,
                threshold_value REAL,
                percentile REAL,
                grid_json TEXT NOT NULL,
                cells_json TEXT NOT NULL,
                contours_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fault_trees (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                root_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fault_tree_evaluations (
                id TEXT PRIMARY KEY,
                fault_tree_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                result_json TEXT NOT NULL,
                FOREIGN KEY (fault_tree_id) REFERENCES fault_trees(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS mocs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                change_type TEXT NOT NULL,
                baseline_scenario_id TEXT,
                proposed_scenario_id TEXT,
                status TEXT NOT NULL,
                risk_level TEXT,
                requires_full_moc INTEGER,
                verification_notes TEXT
            );

            CREATE TABLE IF NOT EXISTS moc_approvals (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                moc_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                comment TEXT,
                FOREIGN KEY (moc_id) REFERENCES mocs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS moc_actions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                moc_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                owner TEXT,
                due_date TEXT,
                status TEXT NOT NULL,
                FOREIGN KEY (moc_id) REFERENCES mocs(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                report_type TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                status TEXT NOT NULL,
                download_url TEXT
            );

            CREATE TABLE IF NOT EXISTS pipeline_routes (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                points_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL,
                etag TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL,
                result_resource_id TEXT,
                error_json TEXT,
                result_json TEXT NOT NULL
            );
            """
        )
        _seed_constants(conn)
        conn.commit()


def _seed_constants(connection: sqlite3.Connection) -> None:
    count = int(connection.execute("SELECT COUNT(*) FROM constants").fetchone()[0])
    if count == 0:
        registry = _read_json("constants_registry.json")["constants"]
        connection.executemany(
            """
            INSERT INTO constants (name, value, unit, description, physical_meaning, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    name,
                    float(definition["value"]),
                    str(definition["unit"]),
                    str(definition["description"]),
                    str(definition["physical_meaning"]) if definition.get("physical_meaning") else None,
                    str(definition.get("source", "default")),
                )
                for name, definition in registry.items()
            ],
        )

    mapping_count = int(connection.execute("SELECT COUNT(*) FROM model_constants").fetchone()[0])
    if mapping_count == 0:
        rows = [
            (model_id, constant_name)
            for model_id, constant_names in MODEL_CONSTANTS_SEED.items()
            for constant_name in constant_names
        ]
        connection.executemany(
            "INSERT INTO model_constants (model_id, constant_name) VALUES (?, ?)",
            rows,
        )


@lru_cache(maxsize=None)
def load_materials_registry() -> dict[str, Any]:
    return _read_json("materials_registry.json")


@lru_cache(maxsize=None)
def load_toxic_criteria_registry() -> dict[str, Any]:
    return _read_json("toxic_criteria_registry.json")


@lru_cache(maxsize=None)
def load_constants_registry() -> dict[str, Any]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT name, value, unit, description, physical_meaning, source
        FROM constants
        ORDER BY name
        """
    ).fetchall()
    return {
        "constants": {
            str(row["name"]): {
                "value": float(row["value"]),
                "unit": str(row["unit"]),
                "description": str(row["description"]),
                "physical_meaning": str(row["physical_meaning"]) if row["physical_meaning"] else None,
                "source": str(row["source"]),
            }
            for row in rows
        }
    }


@lru_cache(maxsize=None)
def load_model_constants_registry() -> dict[str, tuple[str, ...]]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT model_id, constant_name
        FROM model_constants
        ORDER BY model_id, constant_name
        """
    ).fetchall()
    mapping: dict[str, list[str]] = {}
    for row in rows:
        mapping.setdefault(str(row["model_id"]), []).append(str(row["constant_name"]))
    return {model_id: tuple(names) for model_id, names in mapping.items()}


def reset_runtime_caches() -> None:
    load_materials_registry.cache_clear()
    load_toxic_criteria_registry.cache_clear()
    load_constants_registry.cache_clear()
    load_model_constants_registry.cache_clear()


def create_pipeline_route(
    *,
    route_id: str,
    name: str,
    description: str | None,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    connection = get_connection()
    timestamp = _utcnow()
    payload = {
        "id": route_id,
        "name": name,
        "description": description,
        "points": points,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    with _DB_LOCK:
        connection.execute(
            """
            INSERT INTO pipeline_routes (id, name, description, points_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                route_id,
                name,
                description,
                json.dumps(points),
                timestamp,
                timestamp,
            ),
        )
        connection.commit()
    return payload


def list_pipeline_routes() -> list[dict[str, Any]]:
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, name, description, points_json, created_at, updated_at
        FROM pipeline_routes
        ORDER BY updated_at DESC, id DESC
        """
    ).fetchall()
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "description": str(row["description"]) if row["description"] else None,
            "points": json.loads(str(row["points_json"])),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]


def get_pipeline_route(route_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id, name, description, points_json, created_at, updated_at
        FROM pipeline_routes
        WHERE id = ?
        """,
        (route_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "description": str(row["description"]) if row["description"] else None,
        "points": json.loads(str(row["points_json"])),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }
