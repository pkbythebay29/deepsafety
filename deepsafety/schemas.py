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
    physical_meaning: str | None = None
    source: str = "default"


class ReferenceMetadata(BaseModel):
    title: str
    url: str | None = None
    notes: str | None = None


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
    references: list[ReferenceMetadata] = Field(default_factory=list)
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


class ScenarioDefinitionRequest(BaseModel):
    incident_type: str
    classification: str
    inventory: dict[str, Any] = Field(default_factory=dict)
    equipment: dict[str, Any] = Field(default_factory=dict)
    failure_mode: str | None = None
    meteorology: dict[str, Any] = Field(default_factory=dict)
    release_height_m: float | None = None
    topography: str | None = None
    release_duration_s: float | None = None
    conservative_mode: bool = False


class ScenarioDefinitionResponse(BaseModel):
    scenario: dict[str, Any]


class ServiceRequest(BaseModel):
    model_type: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class ServiceResponse(BaseModel):
    model_type: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    equations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constants: list[ConstantMetadata] = Field(default_factory=list)
    references: list[ReferenceMetadata] = Field(default_factory=list)


class TemplateSummary(BaseModel):
    id: str
    name: str
    incident_type: str
    summary: str
    default_inventory: dict[str, Any] = Field(default_factory=dict)
    default_equipment: dict[str, Any] = Field(default_factory=dict)
    default_failure_mode: str
    recommended_services: list[str] = Field(default_factory=list)


class VisualizationRequest(BaseModel):
    layer_type: str
    inputs: dict[str, Any] = Field(default_factory=dict)


class VisualizationResponse(BaseModel):
    layer_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ServiceMetadata(BaseModel):
    service_name: str
    model_type: str
    equations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constants: list[ConstantMetadata] = Field(default_factory=list)
    references: list[ReferenceMetadata] = Field(default_factory=list)


class SignAnalysisRequest(BaseModel):
    image_base64: str | None = None
    image_media_type: str | None = None
    observed_text: str | None = None
    locale: str | None = None
    site_context: str | None = None
    topography: str | None = None
    stability_class: str | None = None
    wind_speed_m_s: float | None = None


class SignAnalysisResponse(BaseModel):
    sign_type: str
    confidence: float
    normalized_text: str
    matched_terms: list[str] = Field(default_factory=list)
    asset_type: str
    substance_family: str
    hazard_classes: list[str] = Field(default_factory=list)
    recommended_services: list[str] = Field(default_factory=list)
    recommended_models: dict[str, Any] = Field(default_factory=dict)
    scenario_template_id: str
    scenario_definition_seed: dict[str, Any] = Field(default_factory=dict)
    impact_zone_seed: dict[str, Any] = Field(default_factory=dict)
    required_parameters: list[FieldMetadata] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
