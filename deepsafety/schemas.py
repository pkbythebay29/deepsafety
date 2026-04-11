from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FieldMetadata(BaseModel):
    name: str
    type: str
    description: str
    unit: str | None = None
    required: bool = True
    allowed_values: list[str] = Field(default_factory=list)


class ConstantMetadata(BaseModel):
    name: str
    value: float
    unit: str
    description: str
    source: str = "default"


class ModelSummary(BaseModel):
    id: str
    name: str
    domain: str
    summary: str
    consequence_areas: list[str]
    status: str
    supported_scenarios: list[str] = Field(default_factory=list)
    gis_ready: bool = False


class ModelDetail(ModelSummary):
    equations: list[str] = Field(default_factory=list)
    input_fields: list[FieldMetadata] = Field(default_factory=list)
    output_fields: list[FieldMetadata] = Field(default_factory=list)
    constants: list[ConstantMetadata] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CalculationRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    constants: dict[str, Any] = Field(default_factory=dict)


class CalculationResponse(BaseModel):
    model: ModelSummary
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    constants: list[ConstantMetadata] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GeoPoint(BaseModel):
    latitude: float
    longitude: float
    label: str | None = None


class ReceptorPoint(GeoPoint):
    id: str


class GISScenarioRequest(BaseModel):
    scenario_type: str
    source: GeoPoint
    receptors: list[ReceptorPoint] = Field(default_factory=list)
    model_id: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    constants: dict[str, Any] = Field(default_factory=dict)


class GISReceptorResult(BaseModel):
    id: str
    label: str | None = None
    latitude: float
    longitude: float
    distance_m: float
    outputs: dict[str, Any]


class GISScenarioResponse(BaseModel):
    scenario_type: str
    model: ModelSummary
    source: GeoPoint
    receptors: list[GISReceptorResult] = Field(default_factory=list)
    constants: list[ConstantMetadata] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    geojson: dict[str, Any]


class ImpactCriterion(BaseModel):
    label: str
    threshold: float
    unit: str


class ImpactZoneRequest(BaseModel):
    scenario_type: str
    source: GeoPoint
    asset: dict[str, Any] = Field(default_factory=dict)
    criteria: list[ImpactCriterion] = Field(default_factory=list)
    constants: dict[str, Any] = Field(default_factory=dict)


class ImpactZone(BaseModel):
    label: str
    threshold: float
    unit: str
    radius_m: float
    area_m2: float
    outputs: dict[str, Any] = Field(default_factory=dict)


class ImpactZoneResponse(BaseModel):
    scenario_type: str
    source: GeoPoint
    asset: dict[str, Any] = Field(default_factory=dict)
    model: ModelSummary
    zones: list[ImpactZone] = Field(default_factory=list)
    constants: list[ConstantMetadata] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    geojson: dict[str, Any]
