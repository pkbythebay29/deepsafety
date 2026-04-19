from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from fastapi import APIRouter, Body, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from deepsafety.data_access import get_connection


ScenarioStatus = Literal["draft", "active", "archived"]
AnalysisStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
ScenarioMode = Literal["deterministic", "scenario_triplet", "probabilistic"]
ModelDomain = Literal[
    "source_model",
    "dispersion",
    "fire_explosion",
    "integrated_consequence",
    "fault_tree",
]
UnitsSystem = Literal["si", "us_customary"]
AnalysisType = Literal["source_model", "dispersion", "fire_explosion", "integrated_consequence"]
SamplingMethod = Literal["random", "latin_hypercube"]
HeatmapSourceType = Literal["analysis", "simulation"]
HeatmapType = Literal["deterministic_value", "exceedance_probability", "percentile_contour"]
FaultTreeMode = Literal["deterministic", "probabilistic"]
MocStatus = Literal[
    "draft",
    "submitted",
    "screening",
    "risk_assessment",
    "review",
    "approved",
    "implementation",
    "verification",
    "closed",
    "rejected",
]
MocChangeType = Literal["equipment", "process_conditions", "chemistry", "procedure", "controls"]
MocRiskLevel = Literal["low", "medium", "high"]
MocDecision = Literal["approve", "reject"]
MocActionStatus = Literal["open", "in_progress", "complete", "cancelled"]
ReportType = Literal[
    "scenario_summary",
    "deterministic_analysis",
    "monte_carlo_summary",
    "heatmap_pack",
    "fault_tree_summary",
    "moc_delta",
]
ReportSourceType = Literal["scenario", "analysis", "simulation", "heatmap", "fault_tree", "moc"]


class ResourceMetadata(BaseModel):
    id: str
    created_at: str
    updated_at: str
    version: int
    etag: str | None = None


class Pagination(BaseModel):
    next_page_token: str | None = None
    page_size: int | None = None


class ErrorPayload(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload


class AsyncSubmissionResponse(BaseModel):
    job_id: str
    resource_id: str | None = None
    resource_type: Literal[
        "analysis",
        "simulation",
        "heatmap",
        "fault_tree_evaluation",
        "moc_delta_analysis",
        "report",
    ]


class Job(ResourceMetadata):
    type: str
    status: AnalysisStatus
    progress: float | None = None
    result_resource_id: str | None = None
    error: ErrorResponse | None = None


class ModelProfile(BaseModel):
    domain: ModelDomain
    submodels: list[str] = Field(default_factory=list)
    units_system: UnitsSystem = "si"


class Scenario(ResourceMetadata):
    name: str
    description: str | None = None
    status: ScenarioStatus
    tags: list[str] = Field(default_factory=list)
    model_profile: ModelProfile
    scenario_mode: ScenarioMode = "deterministic"
    inputs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class ScenarioCreateRequest(BaseModel):
    name: str
    description: str | None = None
    model_profile: ModelProfile
    scenario_mode: ScenarioMode = "deterministic"
    inputs: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ScenarioPatchRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    status: ScenarioStatus | None = None
    inputs: dict[str, Any] | None = None
    notes: str | None = None
    model_profile: ModelProfile | None = None
    scenario_mode: ScenarioMode | None = None


class ScenarioCloneRequest(BaseModel):
    name: str | None = None
    include_tags: bool = True


class ScenarioValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    normalized_inputs: dict[str, Any] = Field(default_factory=dict)


class ScenarioListResponse(BaseModel):
    items: list[Scenario] = Field(default_factory=list)
    pagination: Pagination | None = None


class ScenarioVersionListResponse(BaseModel):
    items: list[Scenario] = Field(default_factory=list)


class Analysis(ResourceMetadata):
    scenario_id: str
    analysis_type: AnalysisType
    status: AnalysisStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)


class AnalysisCreateRequest(BaseModel):
    scenario_id: str
    analysis_type: AnalysisType
    outputs_of_interest: list[str] = Field(default_factory=list)


class AnalysisListResponse(BaseModel):
    items: list[Analysis] = Field(default_factory=list)
    pagination: Pagination | None = None


class SamplingSpec(BaseModel):
    method: SamplingMethod
    iterations: int = Field(ge=1)
    seed: int | None = None


class CorrelationSpec(BaseModel):
    a: str
    b: str
    rho: float = Field(ge=-1, le=1)


class PercentileSummary(BaseModel):
    mean: float | None = None
    stddev: float | None = None
    p05: float | None = None
    p10: float | None = None
    p50: float | None = None
    p90: float | None = None
    p95: float | None = None
    p99: float | None = None


class Simulation(ResourceMetadata):
    scenario_id: str
    status: AnalysisStatus
    sampling: SamplingSpec
    outputs_of_interest: list[str] = Field(default_factory=list)
    correlations: list[CorrelationSpec] = Field(default_factory=list)
    summary: dict[str, PercentileSummary] = Field(default_factory=dict)


class SimulationCreateRequest(BaseModel):
    scenario_id: str
    outputs_of_interest: list[str] = Field(default_factory=list)
    correlations: list[CorrelationSpec] = Field(default_factory=list)
    sampling: SamplingSpec
    retain_samples: bool = False


class SimulationListResponse(BaseModel):
    items: list[Simulation] = Field(default_factory=list)
    pagination: Pagination | None = None


class SimulationSample(BaseModel):
    sample_index: int
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class SimulationSampleListResponse(BaseModel):
    items: list[SimulationSample] = Field(default_factory=list)
    pagination: Pagination | None = None


class SensitivityRank(BaseModel):
    input_name: str
    score: float


class OutputSensitivity(BaseModel):
    output_name: str
    rankings: list[SensitivityRank] = Field(default_factory=list)


class SensitivityResult(BaseModel):
    outputs: list[OutputSensitivity] = Field(default_factory=list)


class HeatmapSource(BaseModel):
    type: HeatmapSourceType
    id: str


class HeatmapGrid(BaseModel):
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    dx: float
    dy: float


class HeatmapCell(BaseModel):
    x: float
    y: float
    value: float


class Point2D(BaseModel):
    x: float
    y: float


class Contour(BaseModel):
    percentile: float | None = None
    points: list[Point2D] = Field(default_factory=list)


class Heatmap(ResourceMetadata):
    source: HeatmapSource
    heatmap_type: HeatmapType
    status: AnalysisStatus
    metric: str
    threshold_value: float | None = None
    percentile: float | None = None
    grid: HeatmapGrid
    cells: list[HeatmapCell] = Field(default_factory=list)
    contours: list[Contour] = Field(default_factory=list)


class HeatmapCreateRequest(BaseModel):
    source: HeatmapSource
    heatmap_type: HeatmapType
    metric: str
    threshold_value: float | None = None
    percentile: float | None = None
    grid: HeatmapGrid | None = None


class HeatmapListResponse(BaseModel):
    items: list[Heatmap] = Field(default_factory=list)
    pagination: Pagination | None = None


class FaultTree(ResourceMetadata):
    name: str
    description: str | None = None
    root: dict[str, Any]


class FaultTreeCreateRequest(BaseModel):
    name: str
    description: str | None = None
    root: dict[str, Any]


class FaultTreePatchRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    root: dict[str, Any] | None = None


class FaultTreeEvaluateRequest(BaseModel):
    mode: FaultTreeMode
    iterations: int | None = Field(default=None, ge=1)


class FaultTreeListResponse(BaseModel):
    items: list[FaultTree] = Field(default_factory=list)
    pagination: Pagination | None = None


class Moc(ResourceMetadata):
    title: str
    description: str | None = None
    change_type: MocChangeType
    baseline_scenario_id: str | None = None
    proposed_scenario_id: str | None = None
    status: MocStatus
    risk_level: MocRiskLevel | None = None
    requires_full_moc: bool | None = None


class MocCreateRequest(BaseModel):
    title: str
    description: str | None = None
    change_type: MocChangeType
    baseline_scenario_id: str | None = None
    proposed_scenario_id: str | None = None


class MocPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    proposed_scenario_id: str | None = None


class MocScreenRequest(BaseModel):
    replacement_in_kind: bool | None = None
    impacts: list[
        Literal[
            "pressure",
            "temperature",
            "inventory",
            "hazardous_materials",
            "safeguards",
            "procedures",
            "controls",
        ]
    ] = Field(default_factory=list)


class MocScreenResult(BaseModel):
    requires_full_moc: bool | None = None
    risk_level: MocRiskLevel | None = None
    triggered_requirements: list[str] = Field(default_factory=list)


class MocDeltaAnalysisRequest(BaseModel):
    baseline_scenario_id: str
    proposed_scenario_id: str
    analysis_type: AnalysisType = "integrated_consequence"
    outputs_of_interest: list[str] = Field(default_factory=list)


class MocApprovalRequest(BaseModel):
    decision: MocDecision
    comment: str | None = None


class MocApproval(ResourceMetadata):
    moc_id: str
    decision: MocDecision
    comment: str | None = None


class MocAction(ResourceMetadata):
    moc_id: str
    title: str
    description: str | None = None
    owner: str | None = None
    due_date: str | None = None
    status: MocActionStatus


class MocActionCreateRequest(BaseModel):
    title: str
    description: str | None = None
    owner: str | None = None
    due_date: str | None = None


class MocActionPatchRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    due_date: str | None = None
    status: MocActionStatus | None = None


class MocActionListResponse(BaseModel):
    items: list[MocAction] = Field(default_factory=list)


class MocCloseRequest(BaseModel):
    verification_notes: str | None = None


class MocListResponse(BaseModel):
    items: list[Moc] = Field(default_factory=list)
    pagination: Pagination | None = None


class Report(ResourceMetadata):
    report_type: ReportType
    source_type: ReportSourceType
    source_id: str
    status: AnalysisStatus
    download_url: str | None = None


class ReportCreateRequest(BaseModel):
    report_type: ReportType
    source_type: ReportSourceType
    source_id: str
    format: Literal["pdf", "docx", "json"] = "pdf"


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _etag(version: int) -> str:
    return f'W/"{version}"'


def _new_resource_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _json_loads(payload: str | None, default: Any) -> Any:
    if not payload:
        return default
    return json.loads(payload)


def _page_offset(page_token: str | None) -> int:
    if not page_token:
        return 0
    try:
        return max(int(page_token), 0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid page_token.") from exc


def _pagination(next_offset: int | None, page_size: int) -> Pagination:
    return Pagination(
        next_page_token=str(next_offset) if next_offset is not None else None,
        page_size=page_size,
    )


def _fetchone(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> sqlite3.Row:
    row = connection.execute(query, params).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Resource not found.")
    return row


def _http_conflict(message: str) -> None:
    raise HTTPException(status_code=409, detail=message)


def _check_if_match(current_etag: str, if_match: str | None) -> None:
    if if_match and if_match != current_etag:
        _http_conflict("If-Match precondition failed.")


def _record_idempotent_response(
    connection: sqlite3.Connection,
    scope: str,
    idempotency_key: str | None,
    resource_id: str | None,
    status_code: int,
    response_body: dict[str, Any],
) -> None:
    if not idempotency_key:
        return
    connection.execute(
        """
        INSERT OR REPLACE INTO idempotency_keys (scope, idempotency_key, resource_id, response_json, status_code)
        VALUES (?, ?, ?, ?, ?)
        """,
        (scope, idempotency_key, resource_id, _json_dumps(response_body), status_code),
    )
    connection.commit()


def _replay_idempotent_response(
    connection: sqlite3.Connection,
    scope: str,
    idempotency_key: str | None,
) -> tuple[int, dict[str, Any]] | None:
    if not idempotency_key:
        return None
    row = connection.execute(
        """
        SELECT status_code, response_json
        FROM idempotency_keys
        WHERE scope = ? AND idempotency_key = ?
        """,
        (scope, idempotency_key),
    ).fetchone()
    if row is None:
        return None
    return int(row["status_code"]), json.loads(str(row["response_json"]))


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalized_distribution_mean(distribution: dict[str, Any]) -> float | None:
    distribution_type = str(distribution.get("type", "")).lower()
    if distribution_type in {"normal", "lognormal"}:
        return _coerce_number(distribution.get("mean"))
    if distribution_type == "uniform":
        minimum = _coerce_number(distribution.get("min"))
        maximum = _coerce_number(distribution.get("max"))
        if minimum is not None and maximum is not None:
            return (minimum + maximum) / 2
    if distribution_type in {"triangular", "pert"}:
        minimum = _coerce_number(distribution.get("min"))
        maximum = _coerce_number(distribution.get("max"))
        mode_value = _coerce_number(distribution.get("mode_value"))
        if minimum is not None and maximum is not None and mode_value is not None:
            return (minimum + maximum + mode_value) / 3
    if distribution_type == "beta":
        alpha = _coerce_number(distribution.get("alpha"))
        beta = _coerce_number(distribution.get("beta"))
        if alpha is not None and beta is not None and alpha + beta > 0:
            return alpha / (alpha + beta)
    if distribution_type == "bernoulli":
        return _coerce_number(distribution.get("probability"))
    return None


def _deterministic_input_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind = str(value.get("kind", "")).lower()
    if kind == "scalar":
        return value.get("value")
    if kind == "scenario_triplet":
        return value.get("realistic_case", value.get("best_case"))
    if kind == "distribution":
        mean_value = _normalized_distribution_mean(dict(value.get("distribution", {})))
        return mean_value if mean_value is not None else dict(value.get("distribution", {}))
    if kind == "categorical":
        values = value.get("values", [])
        if isinstance(values, list) and values:
            weighted = sorted(values, key=lambda item: float(item.get("weight", 0.0)), reverse=True)
            return weighted[0].get("value")
    return value


def _sample_from_distribution(rng: random.Random, distribution: dict[str, Any]) -> float:
    distribution_type = str(distribution.get("type", "")).lower()
    if distribution_type == "normal":
        return rng.normalvariate(float(distribution.get("mean", 0.0)), float(distribution.get("stddev", 1.0)))
    if distribution_type == "lognormal":
        return rng.lognormvariate(float(distribution.get("mean", 0.0)), float(distribution.get("stddev", 1.0)))
    if distribution_type == "uniform":
        return rng.uniform(float(distribution.get("min", 0.0)), float(distribution.get("max", 1.0)))
    if distribution_type in {"triangular", "pert"}:
        return rng.triangular(
            float(distribution.get("min", 0.0)),
            float(distribution.get("max", 1.0)),
            float(distribution.get("mode_value", distribution.get("mean", 0.5))),
        )
    if distribution_type == "beta":
        return rng.betavariate(float(distribution.get("alpha", 2.0)), float(distribution.get("beta", 2.0)))
    if distribution_type == "bernoulli":
        probability = float(distribution.get("probability", 0.5))
        return 1.0 if rng.random() <= probability else 0.0
    mean_value = _normalized_distribution_mean(distribution)
    return float(mean_value or 0.0)


def _weighted_choice(rng: random.Random, values: list[dict[str, Any]]) -> Any:
    if not values:
        return None
    total = sum(max(float(item.get("weight", 0.0)), 0.0) for item in values)
    if total <= 0:
        return values[0].get("value")
    pick = rng.random() * total
    cumulative = 0.0
    for item in values:
        cumulative += max(float(item.get("weight", 0.0)), 0.0)
        if pick <= cumulative:
            return item.get("value")
    return values[-1].get("value")


def _sample_input_value(rng: random.Random, value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind = str(value.get("kind", "")).lower()
    if kind == "scalar":
        return value.get("value")
    if kind == "scenario_triplet":
        derived_distribution = str(value.get("derived_distribution", "none")).lower()
        best_case = value.get("best_case")
        realistic_case = value.get("realistic_case")
        worst_case = value.get("worst_case")
        numbers = [_coerce_number(best_case), _coerce_number(realistic_case), _coerce_number(worst_case)]
        if derived_distribution in {"triangular", "pert"} and all(item is not None for item in numbers):
            return rng.triangular(float(numbers[0]), float(numbers[2]), float(numbers[1]))
        return _weighted_choice(
            rng,
            [
                {"value": best_case, "weight": 0.2},
                {"value": realistic_case, "weight": 0.6},
                {"value": worst_case, "weight": 0.2},
            ],
        )
    if kind == "distribution":
        return _sample_from_distribution(rng, dict(value.get("distribution", {})))
    if kind == "categorical":
        return _weighted_choice(rng, list(value.get("values", [])))
    return value


def _flatten_numeric_inputs(inputs: dict[str, Any], sampler: Callable[[Any], Any]) -> dict[str, float]:
    flattened: dict[str, float] = {}
    for key, raw_value in inputs.items():
        sampled = sampler(raw_value)
        number = _coerce_number(sampled)
        if number is not None:
            flattened[key] = number
    return flattened


def _safe_divide(numerator: float, denominator: float, floor: float = 1.0) -> float:
    return numerator / max(denominator, floor)


def _compute_analysis_outputs(
    scenario: Scenario,
    analysis_type: AnalysisType,
    numeric_inputs: dict[str, float],
    all_inputs: dict[str, Any],
) -> dict[str, Any]:
    inventory = numeric_inputs.get("inventory_mass_kg", numeric_inputs.get("inventory", 100.0))
    duration = numeric_inputs.get("duration_s", numeric_inputs.get("release_duration_s", 60.0))
    wind_speed = numeric_inputs.get("wind_speed_m_s", 3.0)
    distance = numeric_inputs.get("distance_m", 50.0)
    temperature = numeric_inputs.get("temperature_k", numeric_inputs.get("temperature", 298.15))
    pressure = numeric_inputs.get("pressure_pa", numeric_inputs.get("pressure", 101325.0))
    energy_factor = numeric_inputs.get("heat_of_combustion_kj_kg", 46_000.0)
    release_rate = max(numeric_inputs.get("release_rate_kg_s", inventory / max(duration, 1.0)), 0.001)
    total_numeric = sum(abs(value) for value in numeric_inputs.values()) or 1.0
    scenario_hash = int(hashlib.sha256(_json_dumps(all_inputs).encode("utf-8")).hexdigest()[:8], 16)
    signal_factor = 1.0 + (scenario_hash % 17) / 25.0

    if analysis_type == "source_model":
        return {
            "release_rate_kg_s": round(release_rate * signal_factor, 6),
            "total_mass_kg": round(inventory, 6),
            "release_duration_s": round(duration, 6),
            "pressure_pa": round(pressure, 6),
            "temperature_k": round(temperature, 6),
        }

    if analysis_type == "dispersion":
        max_concentration = release_rate * 1000.0 / max(wind_speed * math.sqrt(distance + 1.0), 1.0)
        toxic_distance = math.sqrt(max(release_rate, 0.001)) * 35.0 / max(wind_speed, 0.5)
        return {
            "max_concentration": round(max_concentration * signal_factor, 6),
            "toxic_distance_m": round(toxic_distance * signal_factor, 6),
            "arrival_time_s": round(distance / max(wind_speed, 0.1), 6),
            "wind_speed_m_s": round(wind_speed, 6),
        }

    if analysis_type == "fire_explosion":
        heat_flux = energy_factor * release_rate * 0.0002 / max(distance / 10.0, 1.0)
        overpressure = math.sqrt(max(inventory, 1.0)) * 0.8 / max(distance / 25.0, 1.0)
        return {
            "heat_flux_kw_m2": round(heat_flux * signal_factor, 6),
            "overpressure_kpa": round(overpressure * signal_factor, 6),
            "fireball_diameter_m": round(math.sqrt(max(inventory, 1.0)) * 2.4, 6),
        }

    fatality_index = math.log1p(total_numeric) * signal_factor
    thermal_radius = math.sqrt(max(inventory, 1.0)) * 4.2
    toxic_radius = math.sqrt(max(release_rate, 0.001)) * 28.0 / max(wind_speed, 0.5)
    return {
        "fatality_risk_index": round(fatality_index, 6),
        "thermal_impact_radius_m": round(thermal_radius, 6),
        "toxic_impact_radius_m": round(toxic_radius, 6),
        "combined_severity": "high" if fatality_index >= 10 else "medium" if fatality_index >= 5 else "low",
    }


def _summarize_outputs(outputs: dict[str, Any], outputs_of_interest: list[str] | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    selected = outputs_of_interest or list(outputs.keys())
    for key in selected:
        if key in outputs:
            summary[key] = outputs[key]
    if "combined_severity" in outputs:
        summary["combined_severity"] = outputs["combined_severity"]
    return summary


def _validate_scenario_inputs(inputs: dict[str, Any], scenario_mode: str) -> ScenarioValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, Any] = {}
    for key, raw_value in inputs.items():
        normalized[key] = _deterministic_input_value(raw_value)
        if isinstance(raw_value, dict):
            kind = str(raw_value.get("kind", "")).lower()
            if kind not in {"scalar", "scenario_triplet", "distribution", "categorical"}:
                errors.append(f"Input '{key}' has unsupported kind '{raw_value.get('kind')}'.")
            if kind == "scenario_triplet" and scenario_mode == "deterministic":
                warnings.append(f"Input '{key}' uses triplet values in a deterministic scenario.")
    if not inputs:
        warnings.append("Scenario has no inputs; analyses will use screening defaults.")
    return ScenarioValidationResult(valid=not errors, errors=errors, warnings=warnings, normalized_inputs=normalized)


def _resource_metadata_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "version": int(row["version"]),
        "etag": str(row["etag"]),
    }


def _scenario_from_row(row: sqlite3.Row) -> Scenario:
    return Scenario(
        **_resource_metadata_from_row(row),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
        status=str(row["status"]),
        tags=_json_loads(str(row["tags_json"]), []),
        model_profile=ModelProfile(**_json_loads(str(row["model_profile_json"]), {})),
        scenario_mode=str(row["scenario_mode"]),
        inputs=_json_loads(str(row["inputs_json"]), {}),
        notes=str(row["notes"]) if row["notes"] is not None else None,
    )


def _analysis_from_row(row: sqlite3.Row) -> Analysis:
    return Analysis(
        **_resource_metadata_from_row(row),
        scenario_id=str(row["scenario_id"]),
        analysis_type=str(row["analysis_type"]),
        status=str(row["status"]),
        outputs=_json_loads(str(row["outputs_json"]), {}),
        summary=_json_loads(str(row["summary_json"]), {}),
    )


def _simulation_from_row(row: sqlite3.Row) -> Simulation:
    summary = {
        key: PercentileSummary(**value)
        for key, value in _json_loads(str(row["summary_json"]), {}).items()
    }
    return Simulation(
        **_resource_metadata_from_row(row),
        scenario_id=str(row["scenario_id"]),
        status=str(row["status"]),
        sampling=SamplingSpec(**_json_loads(str(row["sampling_json"]), {})),
        outputs_of_interest=_json_loads(str(row["outputs_of_interest_json"]), []),
        correlations=[CorrelationSpec(**item) for item in _json_loads(str(row["correlations_json"]), [])],
        summary=summary,
    )


def _heatmap_from_row(row: sqlite3.Row) -> Heatmap:
    return Heatmap(
        **_resource_metadata_from_row(row),
        source=HeatmapSource(**_json_loads(str(row["source_json"]), {})),
        heatmap_type=str(row["heatmap_type"]),
        status=str(row["status"]),
        metric=str(row["metric"]),
        threshold_value=float(row["threshold_value"]) if row["threshold_value"] is not None else None,
        percentile=float(row["percentile"]) if row["percentile"] is not None else None,
        grid=HeatmapGrid(**_json_loads(str(row["grid_json"]), {})),
        cells=[HeatmapCell(**item) for item in _json_loads(str(row["cells_json"]), [])],
        contours=[Contour(**item) for item in _json_loads(str(row["contours_json"]), [])],
    )


def _fault_tree_from_row(row: sqlite3.Row) -> FaultTree:
    return FaultTree(
        **_resource_metadata_from_row(row),
        name=str(row["name"]),
        description=str(row["description"]) if row["description"] is not None else None,
        root=_json_loads(str(row["root_json"]), {}),
    )


def _moc_from_row(row: sqlite3.Row) -> Moc:
    requires_full_moc = row["requires_full_moc"]
    return Moc(
        **_resource_metadata_from_row(row),
        title=str(row["title"]),
        description=str(row["description"]) if row["description"] is not None else None,
        change_type=str(row["change_type"]),
        baseline_scenario_id=str(row["baseline_scenario_id"]) if row["baseline_scenario_id"] is not None else None,
        proposed_scenario_id=str(row["proposed_scenario_id"]) if row["proposed_scenario_id"] is not None else None,
        status=str(row["status"]),
        risk_level=str(row["risk_level"]) if row["risk_level"] is not None else None,
        requires_full_moc=bool(requires_full_moc) if requires_full_moc is not None else None,
    )


def _moc_approval_from_row(row: sqlite3.Row) -> MocApproval:
    return MocApproval(
        **_resource_metadata_from_row(row),
        moc_id=str(row["moc_id"]),
        decision=str(row["decision"]),
        comment=str(row["comment"]) if row["comment"] is not None else None,
    )


def _moc_action_from_row(row: sqlite3.Row) -> MocAction:
    return MocAction(
        **_resource_metadata_from_row(row),
        moc_id=str(row["moc_id"]),
        title=str(row["title"]),
        description=str(row["description"]) if row["description"] is not None else None,
        owner=str(row["owner"]) if row["owner"] is not None else None,
        due_date=str(row["due_date"]) if row["due_date"] is not None else None,
        status=str(row["status"]),
    )


def _report_from_row(row: sqlite3.Row) -> Report:
    return Report(
        **_resource_metadata_from_row(row),
        report_type=str(row["report_type"]),
        source_type=str(row["source_type"]),
        source_id=str(row["source_id"]),
        status=str(row["status"]),
        download_url=str(row["download_url"]) if row["download_url"] is not None else None,
    )


def _job_from_row(row: sqlite3.Row) -> Job:
    error_json = _json_loads(str(row["error_json"]), None) if row["error_json"] else None
    return Job(
        **_resource_metadata_from_row(row),
        type=str(row["type"]),
        status=str(row["status"]),
        progress=float(row["progress"]) if row["progress"] is not None else None,
        result_resource_id=str(row["result_resource_id"]) if row["result_resource_id"] is not None else None,
        error=ErrorResponse(**error_json) if error_json else None,
    )


def _store_scenario_version(connection: sqlite3.Connection, scenario: Scenario) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO scenario_versions (scenario_id, version, created_at, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (scenario.id, scenario.version, scenario.updated_at, _json_dumps(scenario.model_dump())),
    )


def _create_job(
    connection: sqlite3.Connection,
    job_type: str,
    result_resource_id: str | None,
    result_payload: dict[str, Any],
) -> Job:
    now = _utcnow()
    job_id = _new_resource_id("job")
    connection.execute(
        """
        INSERT INTO jobs (id, created_at, updated_at, version, etag, type, status, progress, result_resource_id, error_json, result_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            now,
            now,
            1,
            _etag(1),
            job_type,
            "completed",
            100.0,
            result_resource_id,
            None,
            _json_dumps(result_payload),
        ),
    )
    row = _fetchone(connection, "SELECT * FROM jobs WHERE id = ?", (job_id,))
    return _job_from_row(row)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = (len(sorted_values) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[int(index)]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _summarize_samples(samples: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    if not samples:
        return {}
    keys = sorted({key for sample in samples for key in sample.keys()})
    summary: dict[str, dict[str, float]] = {}
    for key in keys:
        values = sorted(float(sample[key]) for sample in samples if key in sample)
        if not values:
            continue
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / len(values)
        summary[key] = {
            "mean": round(mean_value, 6),
            "stddev": round(math.sqrt(variance), 6),
            "p05": round(_percentile(values, 0.05), 6),
            "p10": round(_percentile(values, 0.10), 6),
            "p50": round(_percentile(values, 0.50), 6),
            "p90": round(_percentile(values, 0.90), 6),
            "p95": round(_percentile(values, 0.95), 6),
            "p99": round(_percentile(values, 0.99), 6),
        }
    return summary


def _correlation(x_values: list[float], y_values: list[float]) -> float:
    if len(x_values) != len(y_values) or len(x_values) < 2:
        return 0.0
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
    x_var = sum((x - x_mean) ** 2 for x in x_values)
    y_var = sum((y - y_mean) ** 2 for y in y_values)
    if x_var <= 0 or y_var <= 0:
        return 0.0
    return numerator / math.sqrt(x_var * y_var)


def _build_sensitivity(samples: list[SimulationSample]) -> SensitivityResult:
    if not samples:
        return SensitivityResult(outputs=[])
    input_names = sorted({key for sample in samples for key in sample.inputs.keys() if _coerce_number(sample.inputs[key]) is not None})
    output_names = sorted({key for sample in samples for key in sample.outputs.keys() if _coerce_number(sample.outputs[key]) is not None})
    outputs: list[OutputSensitivity] = []
    for output_name in output_names:
        y_values = [float(sample.outputs[output_name]) for sample in samples if output_name in sample.outputs]
        rankings: list[SensitivityRank] = []
        for input_name in input_names:
            paired = [
                (float(sample.inputs[input_name]), float(sample.outputs[output_name]))
                for sample in samples
                if input_name in sample.inputs
                and output_name in sample.outputs
                and _coerce_number(sample.inputs[input_name]) is not None
                and _coerce_number(sample.outputs[output_name]) is not None
            ]
            if len(paired) < 2:
                continue
            x_values, y_corr_values = zip(*paired)
            rankings.append(SensitivityRank(input_name=input_name, score=round(abs(_correlation(list(x_values), list(y_corr_values))), 6)))
        rankings.sort(key=lambda item: item.score, reverse=True)
        outputs.append(OutputSensitivity(output_name=output_name, rankings=rankings))
    return SensitivityResult(outputs=outputs)


def _evaluate_fault_tree_node(node: dict[str, Any], probabilistic: bool) -> float | bool:
    node_type = str(node.get("node_type", "")).lower()
    if node_type == "basic_event":
        probability = float(node.get("probability", 0.0))
        if node.get("distribution"):
            probability = max(0.0, min(1.0, float(_normalized_distribution_mean(dict(node["distribution"])) or probability)))
        return max(0.0, min(1.0, probability)) if probabilistic else probability >= 0.5

    children = [_evaluate_fault_tree_node(child, probabilistic) for child in node.get("children", [])]
    gate_type = str(node.get("gate_type", "or")).lower()
    if probabilistic:
        probabilities = [float(child) for child in children]
        if gate_type == "and":
            result = 1.0
            for probability in probabilities:
                result *= probability
            return result
        product = 1.0
        for probability in probabilities:
            product *= 1.0 - probability
        return 1.0 - product

    boolean_children = [bool(child) for child in children]
    return all(boolean_children) if gate_type == "and" else any(boolean_children)


def _generate_heatmap_cells(grid: HeatmapGrid, magnitude: float, mode: str, threshold_value: float | None) -> tuple[list[dict[str, float]], list[dict[str, Any]]]:
    x = grid.x_min
    cells: list[dict[str, float]] = []
    while x <= grid.x_max + 1e-9:
        y = grid.y_min
        while y <= grid.y_max + 1e-9:
            distance = math.sqrt(x**2 + y**2)
            base_value = magnitude / max(1.0 + distance / 25.0, 1.0)
            if mode == "exceedance_probability":
                threshold = threshold_value if threshold_value is not None else magnitude
                value = max(0.0, min(1.0, base_value / max(threshold, 1e-9)))
            else:
                value = base_value
            cells.append({"x": round(x, 6), "y": round(y, 6), "value": round(value, 6)})
            y += grid.dy
        x += grid.dx

    contour_radius = math.sqrt(max(magnitude, 0.001)) * 8.0
    contours = [
        {
            "percentile": 50.0,
            "points": [
                {"x": round(math.cos(step) * contour_radius, 6), "y": round(math.sin(step) * contour_radius, 6)}
                for step in [2 * math.pi * index / 24 for index in range(25)]
            ],
        }
    ]
    return cells, contours


def _source_metric_value(connection: sqlite3.Connection, source: HeatmapSource, metric: str) -> float:
    if source.type == "analysis":
        row = _fetchone(connection, "SELECT outputs_json, summary_json FROM analyses WHERE id = ?", (source.id,))
        outputs = _json_loads(str(row["outputs_json"]), {})
        summary = _json_loads(str(row["summary_json"]), {})
        value = outputs.get(metric, summary.get(metric))
        number = _coerce_number(value)
        if number is not None:
            return number
    else:
        row = _fetchone(connection, "SELECT summary_json FROM simulations WHERE id = ?", (source.id,))
        summary = _json_loads(str(row["summary_json"]), {})
        if metric in summary:
            metric_summary = summary[metric]
            number = _coerce_number(metric_summary.get("p50"))
            if number is not None:
                return number
        flattened = [value.get("p50") for value in summary.values() if isinstance(value, dict) and value.get("p50") is not None]
        if flattened:
            return float(flattened[0])
    return 1.0


def create_core_analysis_router() -> APIRouter:
    router = APIRouter()

    @router.get("/scenarios", response_model=ScenarioListResponse, tags=["Scenarios"])
    def list_scenarios(
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
        status: ScenarioStatus | None = Query(default=None),
        q: str | None = Query(default=None),
    ) -> ScenarioListResponse:
        connection = get_connection()
        params: list[Any] = []
        where_clauses: list[str] = []
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if q:
            where_clauses.append("(LOWER(name) LIKE ? OR LOWER(COALESCE(description, '')) LIKE ?)")
            search = f"%{q.lower()}%"
            params.extend([search, search])
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        offset = _page_offset(page_token)
        rows = connection.execute(
            f"""
            SELECT * FROM scenarios
            {where_sql}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size + 1, offset]),
        ).fetchall()
        items = [_scenario_from_row(row) for row in rows[:page_size]]
        next_offset = offset + page_size if len(rows) > page_size else None
        return ScenarioListResponse(items=items, pagination=_pagination(next_offset, page_size))

    @router.post("/scenarios", response_model=Scenario, status_code=201, tags=["Scenarios"])
    def create_scenario(
        request: ScenarioCreateRequest,
        response: Response,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> Scenario:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_scenario", idempotency_key)
        if replay is not None:
            response.status_code = replay[0]
            return Scenario(**replay[1])

        now = _utcnow()
        scenario_id = _new_resource_id("scn")
        version = 1
        scenario = Scenario(
            id=scenario_id,
            created_at=now,
            updated_at=now,
            version=version,
            etag=_etag(version),
            name=request.name,
            description=request.description,
            status="draft",
            tags=request.tags,
            model_profile=request.model_profile,
            scenario_mode=request.scenario_mode,
            inputs=request.inputs,
            notes=None,
        )
        connection.execute(
            """
            INSERT INTO scenarios (id, created_at, updated_at, version, etag, name, description, status, tags_json, model_profile_json, scenario_mode, inputs_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario.id,
                scenario.created_at,
                scenario.updated_at,
                scenario.version,
                scenario.etag,
                scenario.name,
                scenario.description,
                scenario.status,
                _json_dumps(scenario.tags),
                _json_dumps(scenario.model_profile.model_dump()),
                scenario.scenario_mode,
                _json_dumps(scenario.inputs),
                scenario.notes,
            ),
        )
        _store_scenario_version(connection, scenario)
        connection.commit()
        _record_idempotent_response(connection, "create_scenario", idempotency_key, scenario.id, 201, scenario.model_dump())
        return scenario

    @router.get("/scenarios/{scenario_id}", response_model=Scenario, tags=["Scenarios"])
    def get_scenario(scenario_id: str) -> Scenario:
        row = _fetchone(get_connection(), "SELECT * FROM scenarios WHERE id = ?", (scenario_id,))
        return _scenario_from_row(row)

    @router.patch("/scenarios/{scenario_id}", response_model=Scenario, tags=["Scenarios"])
    def update_scenario(
        scenario_id: str,
        request: ScenarioPatchRequest = Body(...),
        if_match: str | None = Header(default=None, alias="If-Match"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> Scenario:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"update_scenario:{scenario_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return Scenario(**replay[1])

        current = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)))
        _check_if_match(current.etag or "", if_match)
        patch_data = request.model_dump(exclude_none=True)
        next_version = current.version + 1
        updated = current.model_copy(update=patch_data)
        updated.version = next_version
        updated.updated_at = _utcnow()
        updated.etag = _etag(next_version)

        connection.execute(
            """
            UPDATE scenarios
            SET updated_at = ?, version = ?, etag = ?, name = ?, description = ?, status = ?, tags_json = ?, model_profile_json = ?, scenario_mode = ?, inputs_json = ?, notes = ?
            WHERE id = ?
            """,
            (
                updated.updated_at,
                updated.version,
                updated.etag,
                updated.name,
                updated.description,
                updated.status,
                _json_dumps(updated.tags),
                _json_dumps(updated.model_profile.model_dump()),
                updated.scenario_mode,
                _json_dumps(updated.inputs),
                updated.notes,
                updated.id,
            ),
        )
        _store_scenario_version(connection, updated)
        connection.commit()
        _record_idempotent_response(connection, f"update_scenario:{scenario_id}", idempotency_key, updated.id, 200, updated.model_dump())
        return updated

    @router.delete("/scenarios/{scenario_id}", status_code=204, tags=["Scenarios"])
    def archive_scenario(scenario_id: str) -> Response:
        connection = get_connection()
        current = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)))
        archived = current.model_copy(update={"status": "archived", "updated_at": _utcnow(), "version": current.version + 1, "etag": _etag(current.version + 1)})
        connection.execute(
            "UPDATE scenarios SET status = ?, updated_at = ?, version = ?, etag = ? WHERE id = ?",
            ("archived", archived.updated_at, archived.version, archived.etag, scenario_id),
        )
        _store_scenario_version(connection, archived)
        connection.commit()
        return Response(status_code=204)

    @router.post("/scenarios/{scenario_id}/validate", response_model=ScenarioValidationResult, tags=["Scenarios"])
    def validate_scenario(scenario_id: str) -> ScenarioValidationResult:
        scenario = _scenario_from_row(_fetchone(get_connection(), "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)))
        return _validate_scenario_inputs(scenario.inputs, scenario.scenario_mode)

    @router.post("/scenarios/{scenario_id}/clone", response_model=Scenario, status_code=201, tags=["Scenarios"])
    def clone_scenario(
        scenario_id: str,
        request: ScenarioCloneRequest | None = None,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> Scenario:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"clone_scenario:{scenario_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return Scenario(**replay[1])

        base = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (scenario_id,)))
        payload = request or ScenarioCloneRequest()
        now = _utcnow()
        clone = Scenario(
            id=_new_resource_id("scn"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            name=payload.name or f"{base.name} (Clone)",
            description=base.description,
            status="draft",
            tags=base.tags if payload.include_tags else [],
            model_profile=base.model_profile,
            scenario_mode=base.scenario_mode,
            inputs=base.inputs,
            notes=base.notes,
        )
        connection.execute(
            """
            INSERT INTO scenarios (id, created_at, updated_at, version, etag, name, description, status, tags_json, model_profile_json, scenario_mode, inputs_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clone.id,
                clone.created_at,
                clone.updated_at,
                clone.version,
                clone.etag,
                clone.name,
                clone.description,
                clone.status,
                _json_dumps(clone.tags),
                _json_dumps(clone.model_profile.model_dump()),
                clone.scenario_mode,
                _json_dumps(clone.inputs),
                clone.notes,
            ),
        )
        _store_scenario_version(connection, clone)
        connection.commit()
        _record_idempotent_response(connection, f"clone_scenario:{scenario_id}", idempotency_key, clone.id, 201, clone.model_dump())
        return clone

    @router.get("/scenarios/{scenario_id}/versions", response_model=ScenarioVersionListResponse, tags=["Scenarios"])
    def list_scenario_versions(scenario_id: str) -> ScenarioVersionListResponse:
        rows = get_connection().execute(
            """
            SELECT snapshot_json
            FROM scenario_versions
            WHERE scenario_id = ?
            ORDER BY version DESC
            """,
            (scenario_id,),
        ).fetchall()
        return ScenarioVersionListResponse(items=[Scenario(**json.loads(str(row["snapshot_json"]))) for row in rows])

    @router.get("/analyses", response_model=AnalysisListResponse, tags=["Analyses"])
    def list_analyses(
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
    ) -> AnalysisListResponse:
        connection = get_connection()
        params: list[Any] = []
        where_sql = ""
        if scenario_id:
            where_sql = "WHERE scenario_id = ?"
            params.append(scenario_id)
        offset = _page_offset(page_token)
        rows = connection.execute(
            f"""
            SELECT * FROM analyses
            {where_sql}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size + 1, offset]),
        ).fetchall()
        items = [_analysis_from_row(row) for row in rows[:page_size]]
        next_offset = offset + page_size if len(rows) > page_size else None
        return AnalysisListResponse(items=items, pagination=_pagination(next_offset, page_size))

    @router.post("/analyses", response_model=AsyncSubmissionResponse, status_code=202, tags=["Analyses"])
    def create_analysis(
        request: AnalysisCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> AsyncSubmissionResponse:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_analysis", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return AsyncSubmissionResponse(**replay[1])

        scenario = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (request.scenario_id,)))
        normalized_inputs = {key: _deterministic_input_value(value) for key, value in scenario.inputs.items()}
        numeric_inputs = _flatten_numeric_inputs(scenario.inputs, _deterministic_input_value)
        outputs = _compute_analysis_outputs(scenario, request.analysis_type, numeric_inputs, normalized_inputs)
        summary = _summarize_outputs(outputs, request.outputs_of_interest)
        now = _utcnow()
        analysis = Analysis(
            id=_new_resource_id("anl"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            scenario_id=request.scenario_id,
            analysis_type=request.analysis_type,
            status="completed",
            outputs=outputs,
            summary=summary,
        )
        connection.execute(
            """
            INSERT INTO analyses (id, created_at, updated_at, version, etag, scenario_id, analysis_type, status, outputs_json, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis.id,
                analysis.created_at,
                analysis.updated_at,
                analysis.version,
                analysis.etag,
                analysis.scenario_id,
                analysis.analysis_type,
                analysis.status,
                _json_dumps(analysis.outputs),
                _json_dumps(analysis.summary),
            ),
        )
        job = _create_job(connection, "analysis", analysis.id, analysis.model_dump())
        connection.commit()
        submission = AsyncSubmissionResponse(job_id=job.id, resource_id=analysis.id, resource_type="analysis")
        _record_idempotent_response(connection, "create_analysis", idempotency_key, analysis.id, 202, submission.model_dump())
        return submission

    @router.get("/analyses/{analysis_id}", response_model=Analysis, tags=["Analyses"])
    def get_analysis(analysis_id: str) -> Analysis:
        return _analysis_from_row(_fetchone(get_connection(), "SELECT * FROM analyses WHERE id = ?", (analysis_id,)))

    @router.get("/simulations", response_model=SimulationListResponse, tags=["Simulations"])
    def list_simulations(
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
        scenario_id: str | None = Query(default=None),
    ) -> SimulationListResponse:
        connection = get_connection()
        params: list[Any] = []
        where_sql = ""
        if scenario_id:
            where_sql = "WHERE scenario_id = ?"
            params.append(scenario_id)
        offset = _page_offset(page_token)
        rows = connection.execute(
            f"""
            SELECT * FROM simulations
            {where_sql}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params + [page_size + 1, offset]),
        ).fetchall()
        items = [_simulation_from_row(row) for row in rows[:page_size]]
        next_offset = offset + page_size if len(rows) > page_size else None
        return SimulationListResponse(items=items, pagination=_pagination(next_offset, page_size))

    @router.post("/simulations", response_model=AsyncSubmissionResponse, status_code=202, tags=["Simulations"])
    def create_simulation(
        request: SimulationCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> AsyncSubmissionResponse:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_simulation", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return AsyncSubmissionResponse(**replay[1])

        scenario = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (request.scenario_id,)))
        rng = random.Random(request.sampling.seed if request.sampling.seed is not None else 42)
        sample_models: list[SimulationSample] = []
        numeric_output_samples: list[dict[str, float]] = []
        analysis_type: AnalysisType = (
            scenario.model_profile.domain if scenario.model_profile.domain in {"source_model", "dispersion", "fire_explosion", "integrated_consequence"} else "integrated_consequence"
        )
        for index in range(request.sampling.iterations):
            sampled_inputs = {key: _sample_input_value(rng, value) for key, value in scenario.inputs.items()}
            numeric_inputs = {key: value for key, value in sampled_inputs.items() if _coerce_number(value) is not None}
            outputs = _compute_analysis_outputs(scenario, analysis_type, {key: float(value) for key, value in numeric_inputs.items()}, sampled_inputs)
            sample = SimulationSample(sample_index=index, inputs=sampled_inputs, outputs=outputs)
            sample_models.append(sample)
            numeric_output_samples.append({key: float(value) for key, value in outputs.items() if _coerce_number(value) is not None})

        summary = _summarize_samples(numeric_output_samples)
        now = _utcnow()
        simulation = Simulation(
            id=_new_resource_id("sim"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            scenario_id=request.scenario_id,
            status="completed",
            sampling=request.sampling,
            outputs_of_interest=request.outputs_of_interest,
            correlations=request.correlations,
            summary={key: PercentileSummary(**value) for key, value in summary.items()},
        )
        connection.execute(
            """
            INSERT INTO simulations (id, created_at, updated_at, version, etag, scenario_id, status, sampling_json, outputs_of_interest_json, correlations_json, summary_json, retain_samples)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                simulation.id,
                simulation.created_at,
                simulation.updated_at,
                simulation.version,
                simulation.etag,
                simulation.scenario_id,
                simulation.status,
                _json_dumps(simulation.sampling.model_dump()),
                _json_dumps(simulation.outputs_of_interest),
                _json_dumps([item.model_dump() for item in simulation.correlations]),
                _json_dumps({key: value.model_dump() for key, value in simulation.summary.items()}),
                1 if request.retain_samples else 0,
            ),
        )
        if request.retain_samples:
            connection.executemany(
                """
                INSERT INTO simulation_samples (simulation_id, sample_index, inputs_json, outputs_json)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (simulation.id, sample.sample_index, _json_dumps(sample.inputs), _json_dumps(sample.outputs))
                    for sample in sample_models
                ],
            )
        sensitivity = _build_sensitivity(sample_models)
        connection.execute(
            "INSERT INTO simulation_sensitivity (simulation_id, result_json) VALUES (?, ?)",
            (simulation.id, _json_dumps(sensitivity.model_dump())),
        )
        job = _create_job(connection, "simulation", simulation.id, simulation.model_dump())
        connection.commit()
        submission = AsyncSubmissionResponse(job_id=job.id, resource_id=simulation.id, resource_type="simulation")
        _record_idempotent_response(connection, "create_simulation", idempotency_key, simulation.id, 202, submission.model_dump())
        return submission

    @router.get("/simulations/{simulation_id}", response_model=Simulation, tags=["Simulations"])
    def get_simulation(simulation_id: str) -> Simulation:
        return _simulation_from_row(_fetchone(get_connection(), "SELECT * FROM simulations WHERE id = ?", (simulation_id,)))

    @router.get("/simulations/{simulation_id}/samples", response_model=SimulationSampleListResponse, tags=["Simulations"])
    def list_simulation_samples(
        simulation_id: str,
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
    ) -> SimulationSampleListResponse:
        connection = get_connection()
        offset = _page_offset(page_token)
        rows = connection.execute(
            """
            SELECT sample_index, inputs_json, outputs_json
            FROM simulation_samples
            WHERE simulation_id = ?
            ORDER BY sample_index ASC
            LIMIT ? OFFSET ?
            """,
            (simulation_id, page_size + 1, offset),
        ).fetchall()
        items = [
            SimulationSample(
                sample_index=int(row["sample_index"]),
                inputs=_json_loads(str(row["inputs_json"]), {}),
                outputs=_json_loads(str(row["outputs_json"]), {}),
            )
            for row in rows[:page_size]
        ]
        next_offset = offset + page_size if len(rows) > page_size else None
        return SimulationSampleListResponse(items=items, pagination=_pagination(next_offset, page_size))

    @router.get("/simulations/{simulation_id}/sensitivity", response_model=SensitivityResult, tags=["Simulations"])
    def get_simulation_sensitivity(simulation_id: str) -> SensitivityResult:
        row = _fetchone(get_connection(), "SELECT result_json FROM simulation_sensitivity WHERE simulation_id = ?", (simulation_id,))
        return SensitivityResult(**_json_loads(str(row["result_json"]), {}))

    @router.get("/heatmaps", response_model=HeatmapListResponse, tags=["Heatmaps"])
    def list_heatmaps(
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
        source_type: HeatmapSourceType | None = Query(default=None),
    ) -> HeatmapListResponse:
        connection = get_connection()
        rows = connection.execute(
            """
            SELECT * FROM heatmaps
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        items = [_heatmap_from_row(row) for row in rows]
        if source_type:
            items = [item for item in items if item.source.type == source_type]
        offset = _page_offset(page_token)
        page_items = items[offset : offset + page_size]
        next_offset = offset + page_size if offset + page_size < len(items) else None
        return HeatmapListResponse(items=page_items, pagination=_pagination(next_offset, page_size))

    @router.post("/heatmaps", response_model=AsyncSubmissionResponse, status_code=202, tags=["Heatmaps"])
    def create_heatmap(
        request: HeatmapCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> AsyncSubmissionResponse:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_heatmap", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return AsyncSubmissionResponse(**replay[1])

        grid = request.grid or HeatmapGrid(x_min=-100.0, x_max=100.0, y_min=-100.0, y_max=100.0, dx=25.0, dy=25.0)
        magnitude = _source_metric_value(connection, request.source, request.metric)
        cells, contours = _generate_heatmap_cells(grid, magnitude, request.heatmap_type, request.threshold_value)
        now = _utcnow()
        heatmap = Heatmap(
            id=_new_resource_id("htm"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            source=request.source,
            heatmap_type=request.heatmap_type,
            status="completed",
            metric=request.metric,
            threshold_value=request.threshold_value,
            percentile=request.percentile,
            grid=grid,
            cells=[HeatmapCell(**item) for item in cells],
            contours=[Contour(**item) for item in contours],
        )
        connection.execute(
            """
            INSERT INTO heatmaps (id, created_at, updated_at, version, etag, source_json, heatmap_type, status, metric, threshold_value, percentile, grid_json, cells_json, contours_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                heatmap.id,
                heatmap.created_at,
                heatmap.updated_at,
                heatmap.version,
                heatmap.etag,
                _json_dumps(heatmap.source.model_dump()),
                heatmap.heatmap_type,
                heatmap.status,
                heatmap.metric,
                heatmap.threshold_value,
                heatmap.percentile,
                _json_dumps(heatmap.grid.model_dump()),
                _json_dumps([cell.model_dump() for cell in heatmap.cells]),
                _json_dumps([contour.model_dump() for contour in heatmap.contours]),
            ),
        )
        job = _create_job(connection, "heatmap", heatmap.id, heatmap.model_dump())
        connection.commit()
        submission = AsyncSubmissionResponse(job_id=job.id, resource_id=heatmap.id, resource_type="heatmap")
        _record_idempotent_response(connection, "create_heatmap", idempotency_key, heatmap.id, 202, submission.model_dump())
        return submission

    @router.get("/heatmaps/{heatmap_id}", response_model=Heatmap, tags=["Heatmaps"])
    def get_heatmap(heatmap_id: str) -> Heatmap:
        return _heatmap_from_row(_fetchone(get_connection(), "SELECT * FROM heatmaps WHERE id = ?", (heatmap_id,)))

    @router.get("/fault-trees", response_model=FaultTreeListResponse, tags=["FaultTrees"])
    def list_fault_trees(
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
    ) -> FaultTreeListResponse:
        rows = get_connection().execute(
            "SELECT * FROM fault_trees ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        items = [_fault_tree_from_row(row) for row in rows]
        offset = _page_offset(page_token)
        page_items = items[offset : offset + page_size]
        next_offset = offset + page_size if offset + page_size < len(items) else None
        return FaultTreeListResponse(items=page_items, pagination=_pagination(next_offset, page_size))

    @router.post("/fault-trees", response_model=FaultTree, status_code=201, tags=["FaultTrees"])
    def create_fault_tree(
        request: FaultTreeCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> FaultTree:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_fault_tree", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return FaultTree(**replay[1])
        now = _utcnow()
        fault_tree = FaultTree(
            id=_new_resource_id("ft"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            name=request.name,
            description=request.description,
            root=request.root,
        )
        connection.execute(
            """
            INSERT INTO fault_trees (id, created_at, updated_at, version, etag, name, description, root_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fault_tree.id,
                fault_tree.created_at,
                fault_tree.updated_at,
                fault_tree.version,
                fault_tree.etag,
                fault_tree.name,
                fault_tree.description,
                _json_dumps(fault_tree.root),
            ),
        )
        connection.commit()
        _record_idempotent_response(connection, "create_fault_tree", idempotency_key, fault_tree.id, 201, fault_tree.model_dump())
        return fault_tree

    @router.get("/fault-trees/{fault_tree_id}", response_model=FaultTree, tags=["FaultTrees"])
    def get_fault_tree(fault_tree_id: str) -> FaultTree:
        return _fault_tree_from_row(_fetchone(get_connection(), "SELECT * FROM fault_trees WHERE id = ?", (fault_tree_id,)))

    @router.patch("/fault-trees/{fault_tree_id}", response_model=FaultTree, tags=["FaultTrees"])
    def update_fault_tree(
        fault_tree_id: str,
        request: FaultTreePatchRequest,
        if_match: str | None = Header(default=None, alias="If-Match"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> FaultTree:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"update_fault_tree:{fault_tree_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return FaultTree(**replay[1])
        current = _fault_tree_from_row(_fetchone(connection, "SELECT * FROM fault_trees WHERE id = ?", (fault_tree_id,)))
        _check_if_match(current.etag or "", if_match)
        patch_data = request.model_dump(exclude_none=True)
        updated = current.model_copy(update=patch_data)
        updated.version += 1
        updated.updated_at = _utcnow()
        updated.etag = _etag(updated.version)
        connection.execute(
            """
            UPDATE fault_trees
            SET updated_at = ?, version = ?, etag = ?, name = ?, description = ?, root_json = ?
            WHERE id = ?
            """,
            (
                updated.updated_at,
                updated.version,
                updated.etag,
                updated.name,
                updated.description,
                _json_dumps(updated.root),
                updated.id,
            ),
        )
        connection.commit()
        _record_idempotent_response(connection, f"update_fault_tree:{fault_tree_id}", idempotency_key, updated.id, 200, updated.model_dump())
        return updated

    @router.post("/fault-trees/{fault_tree_id}/evaluate", response_model=AsyncSubmissionResponse, status_code=202, tags=["FaultTrees"])
    def evaluate_fault_tree(
        fault_tree_id: str,
        request: FaultTreeEvaluateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> AsyncSubmissionResponse:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"evaluate_fault_tree:{fault_tree_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return AsyncSubmissionResponse(**replay[1])
        fault_tree = _fault_tree_from_row(_fetchone(connection, "SELECT * FROM fault_trees WHERE id = ?", (fault_tree_id,)))
        result = _evaluate_fault_tree_node(fault_tree.root, probabilistic=request.mode == "probabilistic")
        evaluation_id = _new_resource_id("fte")
        payload = {
            "fault_tree_id": fault_tree_id,
            "mode": request.mode,
            "iterations": request.iterations,
            "result": result,
        }
        connection.execute(
            """
            INSERT INTO fault_tree_evaluations (id, fault_tree_id, created_at, result_json)
            VALUES (?, ?, ?, ?)
            """,
            (evaluation_id, fault_tree_id, _utcnow(), _json_dumps(payload)),
        )
        job = _create_job(connection, "fault_tree_evaluation", evaluation_id, payload)
        connection.commit()
        submission = AsyncSubmissionResponse(job_id=job.id, resource_id=evaluation_id, resource_type="fault_tree_evaluation")
        _record_idempotent_response(connection, f"evaluate_fault_tree:{fault_tree_id}", idempotency_key, evaluation_id, 202, submission.model_dump())
        return submission

    @router.get("/mocs", response_model=MocListResponse, tags=["MOC"])
    def list_mocs(
        page_size: int = Query(default=50, ge=1, le=500),
        page_token: str | None = Query(default=None),
        status: MocStatus | None = Query(default=None),
    ) -> MocListResponse:
        connection = get_connection()
        params: list[Any] = []
        where_sql = ""
        if status:
            where_sql = "WHERE status = ?"
            params.append(status)
        rows = connection.execute(
            f"SELECT * FROM mocs {where_sql} ORDER BY updated_at DESC, id DESC",
            tuple(params),
        ).fetchall()
        items = [_moc_from_row(row) for row in rows]
        offset = _page_offset(page_token)
        page_items = items[offset : offset + page_size]
        next_offset = offset + page_size if offset + page_size < len(items) else None
        return MocListResponse(items=page_items, pagination=_pagination(next_offset, page_size))

    @router.post("/mocs", response_model=Moc, status_code=201, tags=["MOC"])
    def create_moc(
        request: MocCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> Moc:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_moc", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return Moc(**replay[1])
        now = _utcnow()
        moc = Moc(
            id=_new_resource_id("moc"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            title=request.title,
            description=request.description,
            change_type=request.change_type,
            baseline_scenario_id=request.baseline_scenario_id,
            proposed_scenario_id=request.proposed_scenario_id,
            status="draft",
            risk_level=None,
            requires_full_moc=None,
        )
        connection.execute(
            """
            INSERT INTO mocs (id, created_at, updated_at, version, etag, title, description, change_type, baseline_scenario_id, proposed_scenario_id, status, risk_level, requires_full_moc, verification_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                moc.id,
                moc.created_at,
                moc.updated_at,
                moc.version,
                moc.etag,
                moc.title,
                moc.description,
                moc.change_type,
                moc.baseline_scenario_id,
                moc.proposed_scenario_id,
                moc.status,
                moc.risk_level,
                None,
                None,
            ),
        )
        connection.commit()
        _record_idempotent_response(connection, "create_moc", idempotency_key, moc.id, 201, moc.model_dump())
        return moc

    @router.get("/mocs/{moc_id}", response_model=Moc, tags=["MOC"])
    def get_moc(moc_id: str) -> Moc:
        return _moc_from_row(_fetchone(get_connection(), "SELECT * FROM mocs WHERE id = ?", (moc_id,)))

    @router.patch("/mocs/{moc_id}", response_model=Moc, tags=["MOC"])
    def update_moc(
        moc_id: str,
        request: MocPatchRequest,
        if_match: str | None = Header(default=None, alias="If-Match"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> Moc:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"update_moc:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return Moc(**replay[1])
        current = _moc_from_row(_fetchone(connection, "SELECT * FROM mocs WHERE id = ?", (moc_id,)))
        _check_if_match(current.etag or "", if_match)
        updated = current.model_copy(update=request.model_dump(exclude_none=True))
        updated.version += 1
        updated.updated_at = _utcnow()
        updated.etag = _etag(updated.version)
        connection.execute(
            """
            UPDATE mocs
            SET updated_at = ?, version = ?, etag = ?, title = ?, description = ?, proposed_scenario_id = ?
            WHERE id = ?
            """,
            (updated.updated_at, updated.version, updated.etag, updated.title, updated.description, updated.proposed_scenario_id, updated.id),
        )
        connection.commit()
        _record_idempotent_response(connection, f"update_moc:{moc_id}", idempotency_key, updated.id, 200, updated.model_dump())
        return updated

    @router.post("/mocs/{moc_id}/submit", response_model=Moc, tags=["MOC"])
    def submit_moc(
        moc_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> Moc:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"submit_moc:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return Moc(**replay[1])
        current = _moc_from_row(_fetchone(connection, "SELECT * FROM mocs WHERE id = ?", (moc_id,)))
        updated = current.model_copy(update={"status": "submitted", "version": current.version + 1, "updated_at": _utcnow(), "etag": _etag(current.version + 1)})
        connection.execute(
            "UPDATE mocs SET status = ?, updated_at = ?, version = ?, etag = ? WHERE id = ?",
            (updated.status, updated.updated_at, updated.version, updated.etag, updated.id),
        )
        connection.commit()
        _record_idempotent_response(connection, f"submit_moc:{moc_id}", idempotency_key, updated.id, 200, updated.model_dump())
        return updated

    @router.post("/mocs/{moc_id}/screen", response_model=MocScreenResult, tags=["MOC"])
    def screen_moc(
        moc_id: str,
        request: MocScreenRequest | None = None,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> MocScreenResult:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"screen_moc:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return MocScreenResult(**replay[1])
        moc = _moc_from_row(_fetchone(connection, "SELECT * FROM mocs WHERE id = ?", (moc_id,)))
        payload = request or MocScreenRequest()
        impacts = payload.impacts
        impact_count = len(impacts)
        requires_full_moc = impact_count >= 2 or not bool(payload.replacement_in_kind)
        risk_level: MocRiskLevel = "high" if impact_count >= 4 else "medium" if impact_count >= 2 else "low"
        triggered_requirements = [impact.replace("_", " ") for impact in impacts]
        result = MocScreenResult(
            requires_full_moc=requires_full_moc,
            risk_level=risk_level,
            triggered_requirements=triggered_requirements,
        )
        connection.execute(
            """
            UPDATE mocs
            SET status = ?, risk_level = ?, requires_full_moc = ?, updated_at = ?, version = ?, etag = ?
            WHERE id = ?
            """,
            ("screening", risk_level, 1 if requires_full_moc else 0, _utcnow(), moc.version + 1, _etag(moc.version + 1), moc_id),
        )
        connection.commit()
        _record_idempotent_response(connection, f"screen_moc:{moc_id}", idempotency_key, moc_id, 200, result.model_dump())
        return result

    @router.post("/mocs/{moc_id}/delta-analysis", response_model=AsyncSubmissionResponse, status_code=202, tags=["MOC"])
    def create_moc_delta_analysis(
        moc_id: str,
        request: MocDeltaAnalysisRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> AsyncSubmissionResponse:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"moc_delta_analysis:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return AsyncSubmissionResponse(**replay[1])
        baseline = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (request.baseline_scenario_id,)))
        proposed = _scenario_from_row(_fetchone(connection, "SELECT * FROM scenarios WHERE id = ?", (request.proposed_scenario_id,)))
        baseline_outputs = _compute_analysis_outputs(
            baseline,
            request.analysis_type,
            _flatten_numeric_inputs(baseline.inputs, _deterministic_input_value),
            {key: _deterministic_input_value(value) for key, value in baseline.inputs.items()},
        )
        proposed_outputs = _compute_analysis_outputs(
            proposed,
            request.analysis_type,
            _flatten_numeric_inputs(proposed.inputs, _deterministic_input_value),
            {key: _deterministic_input_value(value) for key, value in proposed.inputs.items()},
        )
        delta = {
            key: round(float(proposed_outputs[key]) - float(baseline_outputs.get(key, 0.0)), 6)
            for key in proposed_outputs
            if _coerce_number(proposed_outputs[key]) is not None and _coerce_number(baseline_outputs.get(key)) is not None
        }
        result_id = _new_resource_id("mda")
        payload = {
            "moc_id": moc_id,
            "baseline_scenario_id": request.baseline_scenario_id,
            "proposed_scenario_id": request.proposed_scenario_id,
            "analysis_type": request.analysis_type,
            "baseline_outputs": baseline_outputs,
            "proposed_outputs": proposed_outputs,
            "delta": delta,
        }
        job = _create_job(connection, "moc_delta_analysis", result_id, payload)
        connection.commit()
        submission = AsyncSubmissionResponse(job_id=job.id, resource_id=result_id, resource_type="moc_delta_analysis")
        _record_idempotent_response(connection, f"moc_delta_analysis:{moc_id}", idempotency_key, result_id, 202, submission.model_dump())
        return submission

    @router.post("/mocs/{moc_id}/approvals", response_model=MocApproval, status_code=201, tags=["MOC"])
    def create_moc_approval(
        moc_id: str,
        request: MocApprovalRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> MocApproval:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"moc_approval:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return MocApproval(**replay[1])
        _fetchone(connection, "SELECT * FROM mocs WHERE id = ?", (moc_id,))
        now = _utcnow()
        approval = MocApproval(
            id=_new_resource_id("map"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            moc_id=moc_id,
            decision=request.decision,
            comment=request.comment,
        )
        connection.execute(
            """
            INSERT INTO moc_approvals (id, created_at, updated_at, version, etag, moc_id, decision, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval.id,
                approval.created_at,
                approval.updated_at,
                approval.version,
                approval.etag,
                approval.moc_id,
                approval.decision,
                approval.comment,
            ),
        )
        connection.execute(
            "UPDATE mocs SET status = ?, updated_at = ?, version = version + 1, etag = ? WHERE id = ?",
            ("approved" if request.decision == "approve" else "rejected", _utcnow(), _etag(2), moc_id),
        )
        connection.commit()
        _record_idempotent_response(connection, f"moc_approval:{moc_id}", idempotency_key, approval.id, 201, approval.model_dump())
        return approval

    @router.get("/mocs/{moc_id}/actions", response_model=MocActionListResponse, tags=["MOC"])
    def list_moc_actions(moc_id: str) -> MocActionListResponse:
        rows = get_connection().execute(
            "SELECT * FROM moc_actions WHERE moc_id = ? ORDER BY created_at ASC, id ASC",
            (moc_id,),
        ).fetchall()
        return MocActionListResponse(items=[_moc_action_from_row(row) for row in rows])

    @router.post("/mocs/{moc_id}/actions", response_model=MocAction, status_code=201, tags=["MOC"])
    def create_moc_action(
        moc_id: str,
        request: MocActionCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> MocAction:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"create_moc_action:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return MocAction(**replay[1])
        _fetchone(connection, "SELECT * FROM mocs WHERE id = ?", (moc_id,))
        now = _utcnow()
        action = MocAction(
            id=_new_resource_id("act"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            moc_id=moc_id,
            title=request.title,
            description=request.description,
            owner=request.owner,
            due_date=request.due_date,
            status="open",
        )
        connection.execute(
            """
            INSERT INTO moc_actions (id, created_at, updated_at, version, etag, moc_id, title, description, owner, due_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action.id,
                action.created_at,
                action.updated_at,
                action.version,
                action.etag,
                action.moc_id,
                action.title,
                action.description,
                action.owner,
                action.due_date,
                action.status,
            ),
        )
        connection.commit()
        _record_idempotent_response(connection, f"create_moc_action:{moc_id}", idempotency_key, action.id, 201, action.model_dump())
        return action

    @router.patch("/mocs/{moc_id}/actions/{action_id}", response_model=MocAction, tags=["MOC"])
    def update_moc_action(
        moc_id: str,
        action_id: str,
        request: MocActionPatchRequest,
        if_match: str | None = Header(default=None, alias="If-Match"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> MocAction:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"update_moc_action:{action_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return MocAction(**replay[1])
        current = _moc_action_from_row(_fetchone(connection, "SELECT * FROM moc_actions WHERE id = ? AND moc_id = ?", (action_id, moc_id)))
        _check_if_match(current.etag or "", if_match)
        updated = current.model_copy(update=request.model_dump(exclude_none=True))
        updated.version += 1
        updated.updated_at = _utcnow()
        updated.etag = _etag(updated.version)
        connection.execute(
            """
            UPDATE moc_actions
            SET updated_at = ?, version = ?, etag = ?, title = ?, description = ?, owner = ?, due_date = ?, status = ?
            WHERE id = ? AND moc_id = ?
            """,
            (
                updated.updated_at,
                updated.version,
                updated.etag,
                updated.title,
                updated.description,
                updated.owner,
                updated.due_date,
                updated.status,
                updated.id,
                moc_id,
            ),
        )
        connection.commit()
        _record_idempotent_response(connection, f"update_moc_action:{action_id}", idempotency_key, updated.id, 200, updated.model_dump())
        return updated

    @router.post("/mocs/{moc_id}/close", response_model=Moc, tags=["MOC"])
    def close_moc(
        moc_id: str,
        request: MocCloseRequest | None = None,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> Moc:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, f"close_moc:{moc_id}", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return Moc(**replay[1])
        current = _moc_from_row(_fetchone(connection, "SELECT * FROM mocs WHERE id = ?", (moc_id,)))
        updated = current.model_copy(update={"status": "closed", "version": current.version + 1, "updated_at": _utcnow(), "etag": _etag(current.version + 1)})
        connection.execute(
            """
            UPDATE mocs
            SET status = ?, updated_at = ?, version = ?, etag = ?, verification_notes = ?
            WHERE id = ?
            """,
            (updated.status, updated.updated_at, updated.version, updated.etag, request.verification_notes if request else None, moc_id),
        )
        connection.commit()
        _record_idempotent_response(connection, f"close_moc:{moc_id}", idempotency_key, updated.id, 200, updated.model_dump())
        return updated

    @router.get("/jobs/{job_id}", response_model=Job, tags=["Jobs"])
    def get_job(job_id: str) -> Job:
        return _job_from_row(_fetchone(get_connection(), "SELECT * FROM jobs WHERE id = ?", (job_id,)))

    @router.post("/reports", response_model=AsyncSubmissionResponse, status_code=202, tags=["Reports"])
    def create_report(
        request: ReportCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        response: Response = None,
    ) -> AsyncSubmissionResponse:
        connection = get_connection()
        replay = _replay_idempotent_response(connection, "create_report", idempotency_key)
        if replay is not None:
            if response is not None:
                response.status_code = replay[0]
            return AsyncSubmissionResponse(**replay[1])
        now = _utcnow()
        report = Report(
            id=_new_resource_id("rpt"),
            created_at=now,
            updated_at=now,
            version=1,
            etag=_etag(1),
            report_type=request.report_type,
            source_type=request.source_type,
            source_id=request.source_id,
            status="completed",
            download_url=f"https://api.deepsafety.tech/v1/reports/{request.source_id}-{request.report_type}.{request.format}",
        )
        connection.execute(
            """
            INSERT INTO reports (id, created_at, updated_at, version, etag, report_type, source_type, source_id, status, download_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.id,
                report.created_at,
                report.updated_at,
                report.version,
                report.etag,
                report.report_type,
                report.source_type,
                report.source_id,
                report.status,
                report.download_url,
            ),
        )
        job = _create_job(connection, "report", report.id, report.model_dump())
        connection.commit()
        submission = AsyncSubmissionResponse(job_id=job.id, resource_id=report.id, resource_type="report")
        _record_idempotent_response(connection, "create_report", idempotency_key, report.id, 202, submission.model_dump())
        return submission

    @router.get("/reports/{report_id}", response_model=Report, tags=["Reports"])
    def get_report(report_id: str) -> Report:
        return _report_from_row(_fetchone(get_connection(), "SELECT * FROM reports WHERE id = ?", (report_id,)))

    return router
