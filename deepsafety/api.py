from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from deepsafety.catalog import (
    ModelInputError,
    get_model,
    get_scenario_models,
    list_models,
    run_model,
)
from deepsafety.constants import list_constants, resolve_constants
from deepsafety.dispersion.neutrally_buoyant import calculate_sigma_y, calculate_sigma_z
from deepsafety.gis import circle_polygon, haversine_distance_m, point_feature
from deepsafety.schemas import (
    CalculationRequest,
    CalculationResponse,
    ConstantMetadata,
    FieldMetadata,
    GISReceptorResult,
    GISScenarioRequest,
    GISScenarioResponse,
    ImpactZone,
    ImpactZoneRequest,
    ImpactZoneResponse,
    ModelDetail,
    ModelSummary,
)


DEFAULT_SCENARIO_MODELS = {
    "leak": "dispersion.gaussian_puff_ground",
    "fire": "fire.point_source_heat_flux",
}
DEFAULT_IMPACT_MODELS = {
    "leak": "dispersion.gaussian_puff_screening_radius",
    "fire": "fire.point_source_heat_flux_radius",
}


def _to_constant_metadata(
    constants: dict[str, dict[str, object]],
) -> list[ConstantMetadata]:
    return [
        ConstantMetadata(
            name=name,
            value=float(definition["value"]),
            unit=str(definition["unit"]),
            description=str(definition["description"]),
            source=str(definition.get("source", "default")),
        )
        for name, definition in constants.items()
    ]


def _to_model_summary(model) -> ModelSummary:
    return ModelSummary(
        id=model.id,
        name=model.name,
        domain=model.domain,
        summary=model.summary,
        consequence_areas=list(model.consequence_areas),
        status=model.status,
        supported_scenarios=list(model.supported_scenarios),
        gis_ready=model.gis_ready,
    )


def _to_model_detail(model) -> ModelDetail:
    resolved_constants = resolve_constants(model.id, {})
    return ModelDetail(
        **_to_model_summary(model).model_dump(),
        equations=list(model.equations),
        input_fields=[
            FieldMetadata(
                name=field.name,
                type=field.type,
                description=field.description,
                unit=field.unit,
                required=field.required,
                allowed_values=list(field.allowed_values),
            )
            for field in model.input_fields
        ],
        output_fields=[
            FieldMetadata(
                name=field.name,
                type=field.type,
                description=field.description,
                unit=field.unit,
                required=field.required,
                allowed_values=list(field.allowed_values),
            )
            for field in model.output_fields
        ],
        constants=_to_constant_metadata(resolved_constants),
        notes=list(model.notes),
    )


def _execute_model(model_id: str, request: CalculationRequest) -> CalculationResponse:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found.")

    try:
        outputs, resolved_constants = run_model(model_id, request.inputs, request.constants)
    except NotImplementedError as exc:
        raise HTTPException(
            status_code=501,
            detail=(
                f"Model '{model_id}' is registered but not implemented yet. "
                "Use /models to inspect current coverage."
            ),
        ) from exc
    except ModelInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return CalculationResponse(
        model=_to_model_summary(model),
        inputs=request.inputs,
        outputs=outputs,
        constants=_to_constant_metadata(resolved_constants),
        equations=list(model.equations),
        warnings=list(model.notes),
    )


def _build_gis_inputs(
    model_id: str,
    distance_m: float,
    base_inputs: dict[str, object],
) -> dict[str, object]:
    inputs = dict(base_inputs)

    if model_id == "dispersion.gaussian_puff_ground":
        inputs.setdefault("x", distance_m)
        inputs.setdefault("y", 0.0)
        inputs.setdefault("z", 0.0)
        stability_class = inputs.get("stability_class")
        if isinstance(stability_class, str):
            if "sigma_y" not in inputs:
                inputs["sigma_y"] = calculate_sigma_y(distance_m, stability_class)
            if "sigma_z" not in inputs:
                inputs["sigma_z"] = calculate_sigma_z(distance_m, stability_class)
    elif model_id == "fire.point_source_heat_flux":
        inputs.setdefault("distance_m", distance_m)

    return inputs


def _build_impact_inputs(
    scenario_type: str,
    asset: dict[str, object],
    threshold: float,
) -> tuple[str, dict[str, object]]:
    if scenario_type == "fire":
        return (
            DEFAULT_IMPACT_MODELS["fire"],
            {
                "burning_rate_kg_s": asset.get("burning_rate_kg_s"),
                "heat_of_combustion_kj_kg": asset.get("heat_of_combustion_kj_kg"),
                "impact_threshold_kw_m2": threshold,
            },
        )

    released_mass_kg = asset.get("released_mass_kg")
    if released_mass_kg is None:
        mass_flow = asset.get("mass_flow_kg_s")
        leak_duration = asset.get("leak_duration_s")
        if mass_flow is None or leak_duration is None:
            raise ModelInputError(
                "Leak impact zones require either 'released_mass_kg' or both 'mass_flow_kg_s' and 'leak_duration_s'."
            )
        released_mass_kg = float(mass_flow) * float(leak_duration)

    return (
        DEFAULT_IMPACT_MODELS["leak"],
        {
            "released_mass_kg": released_mass_kg,
            "concentration_threshold_kg_m3": threshold,
            "stability_class": asset.get("stability_class", "D"),
            "y": asset.get("y", 0.0),
            "z": asset.get("z", 0.0),
        },
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="DeepSafety Consequence Analysis API",
        version="0.1.0",
        summary="Integration-ready process safety consequence calculations.",
        description=(
            "Expose process-safety consequence models through a stable REST API. "
            "The service is designed so client applications can discover available "
            "models, inspect equations and constants, and call calculations with a "
            "consistent request and response structure."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "DeepSafety Consequence Analysis API",
            "version": "0.1.0",
            "docs": "/docs",
            "models_endpoint": "/models",
            "gis_endpoint": "/gis/scenarios/evaluate",
            "impact_zones_endpoint": "/gis/impact-zones",
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/models", response_model=list[ModelSummary])
    def get_models(
        include_planned: bool = Query(
            default=True,
            description="Include planned consequence-analysis models alongside implemented ones.",
        )
    ) -> list[ModelSummary]:
        return [_to_model_summary(model) for model in list_models(include_planned)]

    @app.get("/models/{model_id}", response_model=ModelDetail)
    def get_model_detail(model_id: str) -> ModelDetail:
        model = get_model(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found.")
        return _to_model_detail(model)

    @app.get("/constants", response_model=list[ConstantMetadata])
    def get_constants() -> list[ConstantMetadata]:
        all_constants = {
            name: {
                **definition,
                "source": "default",
            }
            for name, definition in list_constants().items()
        }
        return _to_constant_metadata(all_constants)

    @app.get("/constants/{model_id}", response_model=list[ConstantMetadata])
    def get_model_constants(model_id: str) -> list[ConstantMetadata]:
        model = get_model(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found.")
        return _to_constant_metadata(resolve_constants(model_id, {}))

    @app.get("/scenarios")
    def get_scenarios() -> dict[str, object]:
        return {
            scenario_type: {
                "default_model_id": default_model_id,
                "models": [
                    _to_model_summary(model).model_dump()
                    for model in get_scenario_models(scenario_type)
                ],
            }
            for scenario_type, default_model_id in DEFAULT_SCENARIO_MODELS.items()
        }

    @app.post("/models/{model_id}/calculate", response_model=CalculationResponse)
    def calculate(model_id: str, request: CalculationRequest) -> CalculationResponse:
        return _execute_model(model_id, request)

    @app.post("/gis/scenarios/evaluate", response_model=GISScenarioResponse)
    def evaluate_gis_scenario(request: GISScenarioRequest) -> GISScenarioResponse:
        scenario_type = request.scenario_type.lower()
        model_id = request.model_id or DEFAULT_SCENARIO_MODELS.get(scenario_type)
        if model_id is None:
            raise HTTPException(status_code=400, detail="Unsupported scenario type.")

        model = get_model(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found.")
        if not model.gis_ready:
            raise HTTPException(
                status_code=400,
                detail=f"Model '{model_id}' is not GIS-enabled.",
            )

        receptor_results: list[GISReceptorResult] = []
        geojson_features = [
            point_feature(
                request.source.latitude,
                request.source.longitude,
                {
                    "role": "source",
                    "label": request.source.label or "Source",
                    "scenario_type": scenario_type,
                },
            )
        ]

        resolved_constants = resolve_constants(model_id, request.constants)

        for receptor in request.receptors:
            distance_m = haversine_distance_m(
                request.source.latitude,
                request.source.longitude,
                receptor.latitude,
                receptor.longitude,
            )
            model_inputs = _build_gis_inputs(model_id, distance_m, request.inputs)

            try:
                outputs, _ = run_model(model_id, model_inputs, request.constants)
            except NotImplementedError as exc:
                raise HTTPException(status_code=501, detail=str(exc)) from exc
            except ModelInputError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            receptor_result = GISReceptorResult(
                id=receptor.id,
                label=receptor.label,
                latitude=receptor.latitude,
                longitude=receptor.longitude,
                distance_m=round(distance_m, 3),
                outputs=outputs,
            )
            receptor_results.append(receptor_result)
            geojson_features.append(
                point_feature(
                    receptor.latitude,
                    receptor.longitude,
                    {
                        "role": "receptor",
                        "id": receptor.id,
                        "label": receptor.label,
                        "distance_m": receptor_result.distance_m,
                        **outputs,
                    },
                )
            )

        return GISScenarioResponse(
            scenario_type=scenario_type,
            model=_to_model_summary(model),
            source=request.source,
            receptors=receptor_results,
            constants=_to_constant_metadata(resolved_constants),
            equations=list(model.equations),
            geojson={"type": "FeatureCollection", "features": geojson_features},
        )

    @app.post("/gis/impact-zones", response_model=ImpactZoneResponse)
    def get_impact_zones(request: ImpactZoneRequest) -> ImpactZoneResponse:
        scenario_type = request.scenario_type.lower()
        if scenario_type not in DEFAULT_IMPACT_MODELS:
            raise HTTPException(status_code=400, detail="Unsupported scenario type.")

        model_id = DEFAULT_IMPACT_MODELS[scenario_type]
        model = get_model(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found.")

        zones: list[ImpactZone] = []
        geojson_features = [
            point_feature(
                request.source.latitude,
                request.source.longitude,
                {
                    "role": "source",
                    "label": request.source.label or "Source",
                    "scenario_type": scenario_type,
                    **request.asset,
                },
            )
        ]

        resolved_constants = resolve_constants(model_id, request.constants)

        for criterion in request.criteria:
            try:
                _, model_inputs = _build_impact_inputs(
                    scenario_type,
                    request.asset,
                    criterion.threshold,
                )
                outputs, _ = run_model(model_id, model_inputs, request.constants)
            except NotImplementedError as exc:
                raise HTTPException(status_code=501, detail=str(exc)) from exc
            except ModelInputError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            zone = ImpactZone(
                label=criterion.label,
                threshold=criterion.threshold,
                unit=criterion.unit,
                radius_m=float(outputs["impact_radius_m"]),
                area_m2=float(outputs["impact_area_m2"]),
                outputs=outputs,
            )
            zones.append(zone)
            geojson_features.append(
                circle_polygon(
                    request.source.latitude,
                    request.source.longitude,
                    zone.radius_m,
                    {
                        "role": "impact_zone",
                        "label": criterion.label,
                        "threshold": criterion.threshold,
                        "unit": criterion.unit,
                        "radius_m": zone.radius_m,
                        "area_m2": zone.area_m2,
                        "scenario_type": scenario_type,
                    },
                )
            )

        return ImpactZoneResponse(
            scenario_type=scenario_type,
            source=request.source,
            asset=request.asset,
            model=_to_model_summary(model),
            zones=zones,
            constants=_to_constant_metadata(resolved_constants),
            equations=list(model.equations),
            geojson={"type": "FeatureCollection", "features": geojson_features},
        )

    return app


def main() -> None:
    import uvicorn

    uvicorn.run("deepsafety.api:app", host="127.0.0.1", port=8000, reload=False)


app = create_app()
