from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from deepsafety.catalog import (
    ModelInputError,
    get_model,
    get_scenario_models,
    list_models,
    run_model,
)
from deepsafety.constants import list_constants, resolve_constants
from deepsafety.dispersion.neutrally_buoyant import calculate_sigma_y, calculate_sigma_z
from deepsafety.dispersion_service import solve_dispersion_model
from deepsafety.effect_models import solve_effect_model
from deepsafety.fire_explosion_models import solve_fire_explosion_model
from deepsafety.gis import circle_polygon, haversine_distance_m, point_feature
from deepsafety.scenario_engine import build_scenario_definition
from deepsafety.scenario_library import list_templates
from deepsafety.source_models import solve_source_model
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
    ReferenceMetadata,
    ScenarioDefinitionRequest,
    ScenarioDefinitionResponse,
    ServiceMetadata,
    ServiceRequest,
    ServiceResponse,
    TemplateSummary,
    VisualizationRequest,
    VisualizationResponse,
)
from deepsafety.visualization import build_visualization_layer


DEFAULT_SCENARIO_MODELS = {
    "leak": "dispersion.gaussian_puff_ground",
    "fire": "fire.point_source_heat_flux",
}
DEFAULT_IMPACT_MODELS = {
    "leak": "dispersion.gaussian_puff_screening_radius",
    "fire": "fire.point_source_heat_flux_radius",
}
SOURCE_MODEL_METADATA = {
    "gas_release": {
        "equations": [
            "m_dot = C_d * A * P_0 * sqrt(k / (Z * R * T_0) * (2 / (k + 1))^((k + 1) / (k - 1))) for choked flow",
            "m_dot = C_d * A * P_0 * sqrt((2*k)/(Z*R*T_0*(k-1)) * (r^(2/k) - r^((k+1)/k))) for non-choked flow",
        ],
        "assumptions": [
            "Ideal-gas compressible discharge screening relation.",
            "Pipe and hole releases share the same orifice-style discharge core with user-supplied geometry.",
        ],
        "constants": [
            {
                "name": "shared.gravity_standard",
                "value": 9.80665,
                "unit": "m/s^2",
                "description": "Standard gravity used in liquid and discharge relations.",
                "source": "default",
            },
            {
                "name": "shared.universal_gas_constant",
                "value": 8.314462618,
                "unit": "J/mol/K",
                "description": "Universal gas constant used to derive gas-specific constants.",
                "source": "default",
            },
        ],
        "references": [
            {
                "title": "Crowl and Louvar source term screening relations",
                "notes": "Compressible and incompressible release screening equations reflected in API service metadata.",
            }
        ],
    },
    "liquid_release": {
        "equations": [
            "v = C_d * sqrt(2 * g * h) for gravity-driven discharge",
            "v = C_d * sqrt(2 * DeltaP / rho) for pressurized liquid release",
        ],
        "assumptions": [
            "Incompressible liquid screening model.",
        ],
        "constants": [
            {
                "name": "shared.gravity_standard",
                "value": 9.80665,
                "unit": "m/s^2",
                "description": "Standard gravity used in gravity-driven discharge.",
                "source": "default",
            }
        ],
        "references": [
            {
                "title": "Crowl and Louvar liquid discharge screening relations",
                "notes": "Tank and pipe liquid release equations documented here for API consumers.",
            }
        ],
    },
    "flashing": {
        "equations": [
            "flash_fraction = cp_liquid * (T_storage - T_boil) / latent_heat",
        ],
        "assumptions": [
            "Single-step equilibrium-style flash estimate.",
        ],
        "references": [
            {
                "title": "Crowl and Louvar flashing liquid screening method",
                "notes": "Flash fraction endpoint uses a simple thermodynamic screening relation rather than a full EOS flash calculation.",
            }
        ],
    },
    "pool_formation": {
        "equations": [
            "pool_area = mass / (rho * pool_thickness)",
        ],
        "assumptions": [
            "Uniform pool thickness screening model.",
        ],
        "references": [
            {
                "title": "Pool spreading screening approximation",
                "notes": "Pool area is estimated from volume and layer thickness, then clipped by containment area if supplied.",
            }
        ],
    },
    "evaporation": {
        "equations": [
            "m_dot = q'' * A / latent_heat for heat-transfer-limited evaporation",
            "m_dot = k_m * A * C_s for mass-transfer-limited evaporation",
        ],
        "assumptions": [
            "Surface-limited evaporation screening model.",
        ],
        "references": [
            {
                "title": "Heat-transfer and mass-transfer limited evaporation screening",
                "notes": "The endpoint exposes which evaporation mechanism is in use for transparency.",
            }
        ],
    },
}
DISPERSION_MODEL_METADATA = {
    "gaussian_plume": {
        "equations": [
            "C = Q_dot / (2 * pi * u * sigma_y * sigma_z) * exp(-(y^2)/(2*sigma_y^2)) * [exp(-(z-H)^2/(2*sigma_z^2)) + exp(-(z+H)^2/(2*sigma_z^2))]",
        ],
        "assumptions": [
            "Steady-state continuous release screening model.",
        ],
        "references": [
            {
                "title": "Pasquill-Gifford Gaussian plume screening approach",
                "notes": "Continuous release Gaussian plume with ground reflection and simplified sigma correlations.",
            }
        ],
    },
    "gaussian_puff": {
        "equations": [
            "C = Q / (((2 * pi)^(3/2)) * sigma_y * sigma_z) * exp(-0.5 * ((y / sigma_y)^2 + (z / sigma_z)^2))",
        ],
        "assumptions": [
            "Instantaneous puff screening model.",
        ],
        "references": [
            {
                "title": "Pasquill-Gifford Gaussian puff screening approach",
                "notes": "Instantaneous puff relation used for screening concentration at a receptor.",
            }
        ],
    },
    "dense_gas": {
        "equations": [
            "Screening box/slumping relation using cloud volume, density ratio, and reduced gravity.",
        ],
        "assumptions": [
            "Dense gas endpoint is a screening approximation, not a full heavy-gas CFD model.",
        ],
        "references": [
            {
                "title": "Dense gas slumping screening approximation",
                "notes": "Heavy-gas behavior is represented by a reduced-gravity slumping proxy for fast API evaluation.",
            }
        ],
    },
}
FIRE_EXPLOSION_METADATA = {
    "jet_fire": {
        "equations": ["q = chi_r * m_dot * DeltaH_c / (4 * pi * r^2)"],
        "assumptions": ["Point-source radiation screening for jet fire impacts."],
        "references": [
            {
                "title": "Point-source fire radiation screening model",
                "notes": "Used for fast jet fire impact estimates.",
            }
        ],
    },
    "pool_fire": {
        "equations": ["m_dot = A_pool * m''", "q = chi_r * m_dot * DeltaH_c / (4 * pi * r^2)"],
        "assumptions": ["Pool fire heat flux is treated with a point-source radiation approximation."],
        "references": [
            {
                "title": "Pool fire screening relations",
                "notes": "Burning rate and point-source radiation approximation are exposed explicitly.",
            }
        ],
    },
    "fireball_bleve": {
        "equations": ["D = 5.8 * M^0.325", "t = 0.45 * M^0.26"],
        "assumptions": ["BLEVE fireball size and duration use common empirical screening relations."],
        "references": [
            {
                "title": "BLEVE fireball empirical screening relations",
                "notes": "Empirical fireball size and duration forms are documented for transparency.",
            }
        ],
    },
    "tnt_equivalency": {
        "equations": ["W_TNT = eta * M * DeltaH_c / H_TNT"],
        "assumptions": ["Explosion converted to TNT equivalent for screening overpressure."],
        "references": [
            {
                "title": "TNT equivalency screening method",
                "notes": "Energy yield is transformed into TNT equivalent for quick overpressure screening.",
            }
        ],
    },
    "multi_energy": {
        "equations": ["Equivalent TNT scaled by user-supplied blast strength factor."],
        "assumptions": ["Multi-energy implementation is screening-level rather than a full chart-based implementation."],
        "references": [
            {
                "title": "Multi-energy screening approximation",
                "notes": "Blast strength is simplified into an equivalent TNT scaling factor for fast API use.",
            }
        ],
    },
    "vce": {
        "equations": ["W_TNT = yield_factor * M_cloud * DeltaH_c / H_TNT"],
        "assumptions": ["Yield factor is driven by ignition delay and congestion for screening."],
        "references": [
            {
                "title": "Vapor cloud explosion screening method",
                "notes": "Yield factor is explicitly driven by cloud size, ignition delay, and congestion proxy inputs.",
            }
        ],
    },
}
EFFECT_MODEL_METADATA = {
    "toxic_probit": {
        "equations": ["Y = a + b * ln(C^n * t)"],
        "assumptions": ["Fatality probability derived from a probit-to-normal conversion."],
        "references": [
            {
                "title": "Toxic probit screening relation",
                "notes": "Dose-response result returned with explicit probit parameters and probability transform.",
            }
        ],
    },
    "thermal_probit": {
        "equations": ["Y = a + b * ln(I^(4/3) * t)"],
        "assumptions": ["Burn probability derived from a thermal probit screening relation."],
        "references": [
            {
                "title": "Thermal probit screening relation",
                "notes": "Thermal load is converted into a screening injury probability using a probit transform.",
            }
        ],
    },
    "explosion_probit": {
        "equations": ["Y = a + b * ln(P)"],
        "assumptions": ["Explosion fatality probability derived from overpressure probit form."],
        "references": [
            {
                "title": "Explosion overpressure probit screening relation",
                "notes": "Overpressure is transformed into a screening fatality probability.",
            }
        ],
    },
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


def _to_reference_metadata(
    references: list[dict[str, object]] | tuple[dict[str, object], ...] | None,
) -> list[ReferenceMetadata]:
    if not references:
        return []
    return [
        ReferenceMetadata(
            title=str(reference["title"]),
            url=str(reference["url"]) if reference.get("url") else None,
            notes=str(reference["notes"]) if reference.get("notes") else None,
        )
        for reference in references
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
        references=[],
        notes=list(model.notes),
    )


def _service_response(
    model_type: str,
    outputs: dict[str, object],
    metadata: dict[str, dict[str, list[str]]],
) -> ServiceResponse:
    details = metadata.get(
        model_type,
        {"equations": [], "assumptions": [], "constants": [], "references": []},
    )
    return ServiceResponse(
        model_type=model_type,
        outputs=outputs,
        equations=details["equations"],
        assumptions=details["assumptions"],
        constants=_to_constant_metadata(
            {
                item["name"]: item
                for item in details.get("constants", [])
            }
        )
        if details.get("constants")
        else [],
        references=_to_reference_metadata(details.get("references", [])),
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
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/")
    def root() -> dict[str, object]:
        return {
            "service": "DeepSafety Consequence Analysis API",
            "version": "0.1.0",
            "docs": "/docs",
            "models_endpoint": "/models",
            "scenario_definition_endpoint": "/scenario-engine/define",
            "scenario_library_endpoint": "/scenario-library/templates",
            "source_endpoint": "/source-models/solve",
            "dispersion_endpoint": "/dispersion-models/solve",
            "fire_explosion_endpoint": "/fire-explosion-models/solve",
            "effects_endpoint": "/effect-models/solve",
            "visualization_endpoint": "/visualization/solve",
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

    @app.post("/scenario-engine/define", response_model=ScenarioDefinitionResponse)
    def define_scenario(request: ScenarioDefinitionRequest) -> ScenarioDefinitionResponse:
        try:
            scenario = build_scenario_definition(request.model_dump(exclude_none=True))
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ScenarioDefinitionResponse(scenario=scenario)

    @app.get("/scenario-library/templates", response_model=list[TemplateSummary])
    def get_scenario_templates() -> list[TemplateSummary]:
        return [TemplateSummary(**template) for template in list_templates()]

    @app.get("/service-catalog")
    def get_service_catalog() -> dict[str, list[ServiceMetadata]]:
        return {
            "source_models": [
                ServiceMetadata(
                    service_name="source_models",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=_to_constant_metadata(
                        {item["name"]: item for item in details.get("constants", [])}
                    )
                    if details.get("constants")
                    else [],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in SOURCE_MODEL_METADATA.items()
            ],
            "dispersion_models": [
                ServiceMetadata(
                    service_name="dispersion_models",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=[],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in DISPERSION_MODEL_METADATA.items()
            ],
            "fire_explosion_models": [
                ServiceMetadata(
                    service_name="fire_explosion_models",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=[],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in FIRE_EXPLOSION_METADATA.items()
            ],
            "effect_models": [
                ServiceMetadata(
                    service_name="effect_models",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=[],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in EFFECT_MODEL_METADATA.items()
            ],
        }

    @app.post("/source-models/solve", response_model=ServiceResponse)
    def solve_source(request: ServiceRequest) -> ServiceResponse:
        try:
            outputs = solve_source_model(request.model_type, request.inputs)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _service_response(request.model_type, outputs, SOURCE_MODEL_METADATA)

    @app.post("/dispersion-models/solve", response_model=ServiceResponse)
    def solve_dispersion(request: ServiceRequest) -> ServiceResponse:
        try:
            outputs = solve_dispersion_model(request.model_type, request.inputs)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _service_response(request.model_type, outputs, DISPERSION_MODEL_METADATA)

    @app.post("/fire-explosion-models/solve", response_model=ServiceResponse)
    def solve_fire_explosion(request: ServiceRequest) -> ServiceResponse:
        try:
            outputs = solve_fire_explosion_model(request.model_type, request.inputs)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _service_response(request.model_type, outputs, FIRE_EXPLOSION_METADATA)

    @app.post("/effect-models/solve", response_model=ServiceResponse)
    def solve_effects(request: ServiceRequest) -> ServiceResponse:
        try:
            outputs = solve_effect_model(request.model_type, request.inputs)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _service_response(request.model_type, outputs, EFFECT_MODEL_METADATA)

    @app.post("/visualization/solve", response_model=VisualizationResponse)
    def solve_visualization(request: VisualizationRequest) -> VisualizationResponse:
        try:
            payload = build_visualization_layer(request.layer_type, request.inputs)
        except (ModelInputError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return VisualizationResponse(layer_type=request.layer_type, payload=payload)

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
