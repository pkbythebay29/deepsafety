from __future__ import annotations

import math
from typing import Any

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
from deepsafety.constants import get_constant_definition, get_constant_value, list_constants, resolve_constants
from deepsafety.dispersion.neutrally_buoyant import calculate_sigma_y, calculate_sigma_z
from deepsafety.dispersion_workflows import (
    evaluate_release_mitigation,
    evaluate_toxic_endpoints,
    get_isopleth,
    run_dense_gas,
    run_gaussian_plume,
    run_gaussian_puff,
)
from deepsafety.dispersion_service import solve_dispersion_model
from deepsafety.effect_models import solve_effect_model
from deepsafety.fire_explosion_models import solve_fire_explosion_model
from deepsafety.gis import circle_polygon, haversine_distance_m, point_feature
from deepsafety.hazard_evaluation import (
    run_checklist,
    run_fmea,
    run_hazop,
    run_inherent_safety_review,
    run_preliminary_hazard_analysis,
    run_relative_ranking,
    run_safety_review,
    run_what_if,
    validate_information_requirements,
)
from deepsafety.health_models import (
    calculate_dilution_ventilation,
    calculate_local_exhaust,
    calculate_twa_exposure,
    convert_concentration,
    estimate_pool_evaporation,
    evaluate_exposure_compliance,
    evaluate_probit,
)
from deepsafety.materials_data import (
    get_material,
    get_material_flammability,
    get_material_reactivity,
    get_material_toxicity,
    list_materials,
)
from deepsafety.prevention_models import (
    solve_area_classification,
    solve_fire_protection_strategy,
    solve_purging_strategy,
    solve_static_electricity_risk,
)
from deepsafety.prevention_response_models import solve_prevention_response_model
from deepsafety.reactivity_models import (
    interpret_calorimetry,
    recommend_reactivity_controls,
    screen_reactivity,
)
from deepsafety.relief_models import (
    analyze_relief_system,
    select_effluent_handling,
    select_relief_device,
    size_deflagration_vent,
    size_external_fire_relief,
    size_gas_vapor_relief,
    size_liquid_relief,
    size_thermal_expansion_relief,
    size_two_phase_relief,
)
from deepsafety.scenario_engine import build_scenario_definition
from deepsafety.scenario_library import list_templates
from deepsafety.sign_intelligence import analyze_sign
from deepsafety.spec_helpers import (
    calculate_loc,
    calculate_multi_energy_blast,
    calculate_tnt_equivalency,
    evaluate_bleve,
    evaluate_flammability_mixture,
    evaluate_ignition_energy,
    evaluate_vce,
)
from deepsafety.source_models import solve_source_model
from deepsafety.source_workflows import apply_conservative_analysis, select_release_scenario
from deepsafety.toxic_criteria import lookup_toxic_criteria
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
    SignAnalysisRequest,
    SignAnalysisResponse,
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


def _constant_entry(name: str) -> dict[str, object]:
    definition = get_constant_definition(name)
    return {
        "name": name,
        "value": float(definition["value"]),
        "unit": str(definition["unit"]),
        "description": str(definition["description"]),
        "physical_meaning": str(definition["physical_meaning"]) if definition.get("physical_meaning") else None,
        "source": str(definition.get("source", "default")),
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
            _constant_entry("shared.gravity_standard"),
            _constant_entry("shared.universal_gas_constant"),
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
            _constant_entry("shared.gravity_standard")
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
    "deflagration_screening": {
        "equations": ["W_TNT = eta_eff * M_cloud * DeltaH_c / H_TNT"],
        "assumptions": ["Effective efficiency is driven by flame speed and confinement for screening."],
        "references": [
            {
                "title": "Deflagration screening approximation",
                "notes": "Fast explosion screening based on flame-speed and confinement proxies.",
            }
        ],
    },
    "detonation_screening": {
        "equations": ["W_TNT = f_det * M_cloud * DeltaH_c / H_TNT"],
        "assumptions": ["Detonation endpoint is a screening approximation using detonable fraction."],
        "references": [
            {
                "title": "Detonation screening approximation",
                "notes": "Used to represent high-severity blast screening without full reactive CFD.",
            }
        ],
    },
    "blast_damage_screening": {
        "equations": ["Damage category selected from overpressure thresholds."],
        "assumptions": ["Structural damage categories are screening bands keyed to overpressure."],
        "references": [
            {
                "title": "Blast damage screening thresholds",
                "notes": "Maps overpressure into minor, moderate, major, and severe screening categories.",
            }
        ],
    },
    "mitigation_screening": {
        "equations": ["P_mitigated = P * (1 - barrier_efficiency) * (1 - 0.5 * venting_factor)"],
        "assumptions": ["Barrier and venting factors are treated as first-pass reduction multipliers."],
        "references": [
            {
                "title": "Explosion mitigation screening approximation",
                "notes": "Used for fast stand-off and mitigation planning studies.",
            }
        ],
    },
}
EFFECT_MODEL_METADATA = {
    "toxic_probit": {
        "equations": ["Y = a + b * ln(C^n * t)"],
        "assumptions": [
            "Fatality probability derived from a probit-to-normal conversion.",
            "Population distribution inputs can be supplied to estimate expected fatalities by exposure zone.",
        ],
        "references": [
            {
                "title": "Toxic probit screening relation",
                "notes": "Dose-response result returned with explicit probit parameters and probability transform.",
            }
        ],
    },
    "toxic_dose_response": {
        "equations": ["Y = a + b * ln(C^n * t)"],
        "assumptions": [
            "Generates a concentration-versus-fatality screening curve at a fixed exposure duration.",
        ],
        "references": [
            {
                "title": "Toxic dose-response screening relation",
                "notes": "Returns curve points so client applications can plot consequence thresholds directly.",
            }
        ],
    },
    "thermal_probit": {
        "equations": ["Y = a + b * ln(I^(4/3) * t)"],
        "assumptions": [
            "Burn probability derived from a thermal probit screening relation.",
            "Population distribution inputs can be supplied to estimate expected burn cases by exposure zone.",
        ],
        "references": [
            {
                "title": "Thermal probit screening relation",
                "notes": "Thermal load is converted into a screening injury probability using a probit transform.",
            }
        ],
    },
    "thermal_dose_response": {
        "equations": ["Y = a + b * ln(I^(4/3) * t)"],
        "assumptions": [
            "Generates a heat-flux-versus-burn-probability screening curve at a fixed exposure duration.",
        ],
        "references": [
            {
                "title": "Thermal dose-response screening relation",
                "notes": "Returns curve points so client applications can plot burn probability against radiation intensity.",
            }
        ],
    },
    "explosion_probit": {
        "equations": ["Y = a + b * ln(P)"],
        "assumptions": [
            "Explosion fatality probability derived from overpressure probit form.",
            "Population distribution inputs can be supplied to estimate expected fatalities by overpressure zone.",
        ],
        "references": [
            {
                "title": "Explosion overpressure probit screening relation",
                "notes": "Overpressure is transformed into a screening fatality probability.",
            }
        ],
    },
    "explosion_dose_response": {
        "equations": ["Y = a + b * ln(P)"],
        "assumptions": [
            "Generates an overpressure-versus-fatality screening curve.",
        ],
        "references": [
            {
                "title": "Explosion dose-response screening relation",
                "notes": "Returns curve points so client applications can plot fatality probability against overpressure.",
            }
        ],
    },
}
SIGN_INTELLIGENCE_METADATA = {
    "sign_analysis": {
        "equations": [
            "Keyword and phrase matching against normalized sign text.",
        ],
        "assumptions": [
            "This service classifies sign meaning from OCR text or manually entered sign text rather than raw pixels.",
            "Returned scenario seeds are intended to accelerate downstream consequence calculations.",
        ],
        "references": [
            {
                "title": "Deep Safety sign intelligence heuristics",
                "notes": "Multilingual keyword screening for pipeline, flammable gas, high-pressure gas, and toxic gas signs.",
            }
        ],
    }
}
TOXIC_CRITERIA_METADATA = {
    "toxic_criteria_lookup": {
        "equations": ["Registry lookup and optional caller override merge for toxic criteria values."],
        "assumptions": [
            "Starter criteria registry is built into the API and can be extended through request overrides.",
        ],
        "references": [
            {
                "title": "Deep Safety toxic criteria registry",
                "notes": "Starter dataset covering AEGL, ERPG, IDLH, TLV, PEL, and toxic endpoint values for selected chemicals.",
            }
        ],
    }
}
PREVENTION_RESPONSE_METADATA = {
    "fire_triangle_screening": {
        "equations": ["Fire possible when fuel, oxidizer, and ignition source are all present."],
        "assumptions": ["Boolean fire triangle screening check."],
        "references": [{"title": "Fire triangle screening"}],
    },
    "autoignition_screening": {
        "equations": ["safety_margin = T_autoignition - T_process"],
        "assumptions": ["Temperature margin used as a screening ignition indicator."],
        "references": [{"title": "Autoignition temperature screening"}],
    },
    "inerting_requirement": {
        "equations": ["V_inert = V_protected * (x_O2,initial - x_O2,target) / purity"],
        "assumptions": ["Well-mixed oxygen dilution screening model."],
        "references": [{"title": "Inerting requirement screening"}],
    },
    "ignition_energy_screening": {
        "equations": ["energy_ratio = E_source / MIE"],
        "assumptions": ["Compares source energy against minimum ignition energy."],
        "references": [{"title": "Minimum ignition energy screening"}],
    },
    "spray_mist_screening": {
        "equations": ["mist_enhancement_factor = (spray_pressure / droplet_size) * (T_liquid / flash_point)"],
        "assumptions": ["Atomization and temperature proxies used for spray/mist fire screening."],
        "references": [{"title": "Spray and mist screening approximation"}],
    },
    "release_prevention_screening": {
        "equations": ["prevention_score = barriers * P_shutdown / (1 + t_detect/60 + t_isolate/60) * (30 / inspection_interval_days)"],
        "assumptions": ["Barrier count, response time, and inspection interval are combined into a screening score."],
        "references": [{"title": "Release prevention screening"}],
    },
    "emergency_response_planning": {
        "equations": ["urgency_score = population_exposed * release_duration / response_team_time"],
        "assumptions": ["Compares shelter and evacuation times to propose an initial protective action."],
        "references": [{"title": "Emergency response planning screening"}],
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
            physical_meaning=str(definition["physical_meaning"]) if definition.get("physical_meaning") else None,
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
        leak_duration = asset.get("duration_s", asset.get("leak_duration_s"))
        mass_flow = asset.get("mass_flow_kg_s")
        if mass_flow is not None and leak_duration is not None:
            released_mass_kg = float(mass_flow) * float(leak_duration)
        elif (
            leak_duration is not None
            and (
                "upstream_pressure_pa" in asset
                or "line_pressure_kpa" in asset
                or "delta_pressure_pa" in asset
                or "density_kg_m3" in asset
            )
        ):
            if "density_kg_m3" in asset and (
                "liquid_head_m" in asset or "delta_pressure_pa" in asset
            ):
                source_inputs = {
                    "density_kg_m3": asset.get("density_kg_m3"),
                    "duration_s": leak_duration,
                    "source_subtype": asset.get("source_subtype", "hole_in_tank"),
                    "discharge_coefficient": asset.get("discharge_coefficient", 0.62),
                    "liquid_head_m": asset.get("liquid_head_m"),
                    "delta_pressure_pa": asset.get("delta_pressure_pa"),
                    "hole_area_m2": asset.get("hole_area_m2"),
                    "hole_diameter_m": asset.get("hole_diameter_m", asset.get("diameter_m")),
                    "pipe_area_m2": asset.get("pipe_area_m2"),
                    "pipe_diameter_m": asset.get("pipe_diameter_m", asset.get("diameter_m")),
                    "pipe_length_m": asset.get("pipe_length_m"),
                    "inventory_mass_kg": asset.get("inventory_mass_kg"),
                    "conservative_mode": asset.get("conservative_mode", False),
                }
                source_inputs = {key: value for key, value in source_inputs.items() if value is not None}
                source_outputs = solve_source_model("liquid_release", source_inputs)
            else:
                source_inputs = {
                    "duration_s": leak_duration,
                    "upstream_pressure_pa": asset.get(
                        "upstream_pressure_pa",
                        float(asset.get("line_pressure_kpa", 0.0)) * 1000.0,
                    ),
                    "downstream_pressure_pa": asset.get("downstream_pressure_pa", 101_325.0),
                    "temperature_k": asset.get(
                        "temperature_k",
                        float(asset.get("gas_temperature_c", 15.0)) + get_constant_value("shared.absolute_zero_offset_c"),
                    ),
                    "heat_capacity_ratio": asset.get("heat_capacity_ratio", 1.3),
                    "molecular_weight_kg_kmol": asset.get("molecular_weight_kg_kmol", 28.97),
                    "discharge_coefficient": asset.get("discharge_coefficient", 0.62),
                    "compressibility": asset.get("compressibility", 1.0),
                    "source_subtype": asset.get(
                        "source_subtype",
                        asset.get("discharge_geometry", "pipe"),
                    ),
                    "pipe_area_m2": asset.get("pipe_area_m2"),
                    "pipe_diameter_m": asset.get("pipe_diameter_m", asset.get("diameter_m")),
                    "pipe_length_m": asset.get("pipe_length_m"),
                    "hole_area_m2": asset.get("hole_area_m2"),
                    "hole_diameter_m": asset.get("hole_diameter_m", asset.get("diameter_m")),
                    "relief_area_m2": asset.get("relief_area_m2"),
                    "relief_diameter_m": asset.get("relief_diameter_m"),
                    "inventory_mass_kg": asset.get("inventory_mass_kg"),
                    "vessel_volume_m3": asset.get("vessel_volume_m3"),
                    "final_pressure_pa": asset.get("final_pressure_pa"),
                    "conservative_mode": asset.get("conservative_mode", False),
                }
                source_inputs = {key: value for key, value in source_inputs.items() if value is not None}
                source_outputs = solve_source_model("gas_release", source_inputs)
            released_mass_kg = float(source_outputs["total_mass_kg"])
        else:
            if mass_flow is None or leak_duration is None:
                raise ModelInputError(
                    "Leak impact zones require either 'released_mass_kg', source-term inputs, or both 'mass_flow_kg_s' and 'leak_duration_s'."
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
        version="1.0.0",
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
            "version": "1.0.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "models_endpoint": "/models",
            "materials_endpoint": "/materials",
            "health_endpoint": "/health/convert-concentration",
            "scenario_definition_endpoint": "/scenario-engine/define",
            "scenario_library_endpoint": "/scenario-library/templates",
            "source_endpoint": "/source-models/solve",
            "source_scenario_select_endpoint": "/source-models/scenario/select",
            "dispersion_endpoint": "/dispersion-models/solve",
            "dispersion_plume_endpoint": "/dispersion/gaussian-plume",
            "fire_explosion_endpoint": "/fire-explosion-models/solve",
            "fire_explosion_vce_endpoint": "/fire-explosion/vce",
            "effects_endpoint": "/effect-models/solve",
            "toxic_criteria_endpoint": "/toxic-criteria/lookup",
            "prevention_response_endpoint": "/prevention-response-models/solve",
            "prevention_endpoint": "/prevention/inerting/purge",
            "reactivity_endpoint": "/reactivity/screening",
            "relief_endpoint": "/relief/system/analyze",
            "hazard_evaluation_endpoint": "/hazard-evaluation/hazop",
            "visualization_endpoint": "/visualization/solve",
            "sign_analysis_endpoint": "/signs/analyze",
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

    @app.get("/materials")
    def materials_endpoint(
        q: str | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        pageSize: int = Query(default=20, ge=1, le=100),
    ) -> dict[str, object]:
        return list_materials(query=q, page=page, page_size=pageSize)

    @app.get("/materials/{material_id}")
    def material_endpoint(material_id: str) -> dict[str, object]:
        try:
            return get_material(material_id)
        except ModelInputError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/materials/{material_id}/toxicity")
    def material_toxicity_endpoint(material_id: str) -> dict[str, object]:
        try:
            return get_material_toxicity(material_id)
        except ModelInputError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/materials/{material_id}/flammability")
    def material_flammability_endpoint(material_id: str) -> dict[str, object]:
        try:
            return get_material_flammability(material_id)
        except ModelInputError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/materials/{material_id}/reactivity")
    def material_reactivity_endpoint(material_id: str) -> dict[str, object]:
        try:
            return get_material_reactivity(material_id)
        except ModelInputError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/health/convert-concentration")
    def convert_concentration_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return convert_concentration(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/health/probit/evaluate")
    def evaluate_probit_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_probit(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/health/exposure/twa")
    def calculate_twa_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return calculate_twa_exposure(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/health/exposure/compliance")
    def evaluate_exposure_compliance_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_exposure_compliance(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/industrial-hygiene/ventilation/dilution")
    def dilution_ventilation_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return calculate_dilution_ventilation(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/industrial-hygiene/ventilation/local-exhaust")
    def local_exhaust_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return calculate_local_exhaust(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/industrial-hygiene/liquid-pool/evaporation")
    def pool_evaporation_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return estimate_pool_evaporation(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            "toxic_criteria": [
                ServiceMetadata(
                    service_name="toxic_criteria",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=[],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in TOXIC_CRITERIA_METADATA.items()
            ],
            "prevention_response_models": [
                ServiceMetadata(
                    service_name="prevention_response_models",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=[],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in PREVENTION_RESPONSE_METADATA.items()
            ],
            "sign_intelligence": [
                ServiceMetadata(
                    service_name="sign_intelligence",
                    model_type=model_type,
                    equations=details.get("equations", []),
                    assumptions=details.get("assumptions", []),
                    constants=[],
                    references=_to_reference_metadata(details.get("references", [])),
                )
                for model_type, details in SIGN_INTELLIGENCE_METADATA.items()
            ],
            "materials": [
                ServiceMetadata(
                    service_name="materials",
                    model_type="material_record",
                    equations=[],
                    assumptions=[
                        "Material records are foundational inputs for source, dispersion, flammability, toxicity, reactivity, and hazard-study workflows."
                    ],
                    constants=[],
                    references=[
                        ReferenceMetadata(
                            title="Material data foundation",
                            notes="Chemical properties, flammability, toxicity, reactivity, equipment, procedures, and operating conditions are all upstream requirements for meaningful hazard evaluation.",
                        )
                    ],
                )
            ],
            "health": [
                ServiceMetadata(
                    service_name="health",
                    model_type="convert_concentration",
                    equations=["ppm <-> mg/m3 via ideal-gas concentration relation"],
                    assumptions=["Ideal-gas conversion at user-supplied temperature and pressure."],
                    constants=[],
                    references=[ReferenceMetadata(title="Concentration unit conversion")],
                ),
                ServiceMetadata(
                    service_name="health",
                    model_type="probit_evaluation",
                    equations=["Y = k1 + k2 * ln(V)"],
                    assumptions=["Probability is obtained from a probit-to-normal transform."],
                    constants=[],
                    references=[ReferenceMetadata(title="Generic probit evaluation")],
                ),
            ],
            "prevention": [
                ServiceMetadata(
                    service_name="prevention",
                    model_type="purging_strategy",
                    equations=["Purge gas requirement scales with vessel volume, purge cycles, and gas purity."],
                    assumptions=["Purging endpoints are screening tools for inerting and oxygen reduction studies."],
                    constants=[],
                    references=[ReferenceMetadata(title="Purging and inerting screening")],
                )
            ],
            "reactivity": [
                ServiceMetadata(
                    service_name="reactivity",
                    model_type="screening",
                    equations=["Qualitative compatibility and temperature-driven reactivity review."],
                    assumptions=["Starter reactivity screening uses incompatibility lists plus process-condition flags."],
                    constants=[],
                    references=[ReferenceMetadata(title="Reactive hazard screening")],
                )
            ],
            "relief": [
                ServiceMetadata(
                    service_name="relief",
                    model_type="device_selection_and_sizing",
                    equations=[
                        "Liquid and gas relief sizing use screening area-capacity relations.",
                        "Deflagration vent sizing scales with enclosure volume and explosion severity factor.",
                    ],
                    assumptions=["Relief-system endpoints are screening-grade, not code-stamped final design calculations."],
                    constants=[],
                    references=[ReferenceMetadata(title="Relief system screening and sizing")],
                )
            ],
            "hazard_evaluation": [
                ServiceMetadata(
                    service_name="hazard_evaluation",
                    model_type="hazop_fmea_what_if",
                    equations=[],
                    assumptions=[
                        "Scenario outputs from source and dispersion services are intended to feed structured hazard-study workflows."
                    ],
                    constants=[],
                    references=[ReferenceMetadata(title="Scenario-based hazard evaluation workflows")],
                )
            ],
        }

    @app.post("/source-models/liquid-hole")
    def source_liquid_hole_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = solve_source_model(
                "liquid_release",
                {
                    "source_subtype": "pipe_flow",
                    "density_kg_m3": payload["liquidDensity"],
                    "delta_pressure_pa": max(float(payload["upstreamPressure"]) - float(payload["downstreamPressure"]), 1.0),
                    "hole_area_m2": payload["holeArea"],
                    "duration_s": 1.0,
                    "inventory_mass_kg": 1e12,
                    "discharge_coefficient": payload.get("dischargeCoefficient", 0.62),
                },
            )
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"releaseRate": result["release_rate_kg_s"], "unit": "kg/s"}

    @app.post("/source-models/tank-hole")
    def source_tank_hole_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            density = float(payload["liquidDensity"])
            liquid_head = float(payload["liquidHead"])
            hole_area = float(payload["holeArea"])
            tank_cross_section_area = float(payload.get("tankCrossSectionArea", 1.0))
            result = solve_source_model(
                "liquid_release",
                {
                    "source_subtype": "hole_in_tank",
                    "density_kg_m3": density,
                    "hole_area_m2": hole_area,
                    "liquid_head_m": liquid_head,
                    "duration_s": 1.0,
                    "inventory_mass_kg": 1e12,
                    "discharge_coefficient": payload.get("dischargeCoefficient", 0.62),
                },
            )
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        initial_release_rate = float(result["release_rate_kg_s"])
        inventory_mass = density * tank_cross_section_area * liquid_head
        emptying_time = inventory_mass / max(initial_release_rate, 1e-9)
        profile = []
        for fraction in [0.0, 0.25, 0.5, 0.75, 1.0]:
            remaining_head = max(liquid_head * (1.0 - fraction), 0.0)
            release_rate = initial_release_rate * (remaining_head / liquid_head) ** 0.5 if liquid_head > 0 else 0.0
            profile.append({"time": round(emptying_time * fraction, 6), "releaseRate": round(release_rate, 6)})
        return {
            "initialReleaseRate": round(initial_release_rate, 6),
            "emptyingTime": round(emptying_time, 6),
            "releaseRateProfile": profile,
        }

    @app.post("/source-models/liquid-pipe")
    def source_liquid_pipe_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            density = float(payload["density"])
            diameter = float(payload["pipeDiameter"])
            viscosity = float(payload["viscosity"])
            roughness = float(payload["roughness"])
            result = solve_source_model(
                "liquid_release",
                {
                    "source_subtype": "pipe_flow",
                    "density_kg_m3": density,
                    "delta_pressure_pa": payload["pressureDrop"],
                    "pipe_diameter_m": diameter,
                    "pipe_length_m": payload["pipeLength"],
                    "pipe_area_m2": 3.141592653589793 * diameter**2 / 4.0,
                    "relative_roughness": roughness / max(diameter, 1e-9),
                    "duration_s": 1.0,
                    "inventory_mass_kg": 1e12,
                },
            )
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        velocity = float(result["exit_velocity_m_s"])
        reynolds = density * velocity * diameter / max(viscosity, 1e-12)
        if reynolds <= 2_000:
            friction_factor = 64.0 / max(reynolds, 1.0)
        else:
            friction_factor = 0.25 / (
                math.log10((roughness / max(diameter, 1e-9)) / 3.7 + 5.74 / reynolds**0.9) ** 2
            )
        return {
            "velocity": round(velocity, 6),
            "massFlowRate": result["release_rate_kg_s"],
            "reynoldsNumber": round(reynolds, 6),
            "frictionFactor": round(friction_factor, 6),
        }

    @app.post("/source-models/gas-hole")
    def source_gas_hole_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = solve_source_model(
                "gas_release",
                {
                    "source_subtype": "hole",
                    "upstream_pressure_pa": payload["upstreamPressure"],
                    "downstream_pressure_pa": payload["downstreamPressure"],
                    "temperature_k": payload["temperatureK"],
                    "molecular_weight_kg_kmol": payload["molecularWeight"],
                    "heat_capacity_ratio": payload["heatCapacityRatio"],
                    "hole_area_m2": payload["holeArea"],
                    "discharge_coefficient": payload.get("dischargeCoefficient", 0.62),
                    "duration_s": 1.0,
                    "inventory_mass_kg": 1e12,
                },
            )
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        gas_constant = get_constant_value("shared.universal_gas_constant") / (float(payload["molecularWeight"]) / 1000.0)
        sonic_velocity = (float(payload["heatCapacityRatio"]) * gas_constant * float(payload["temperatureK"])) ** 0.5
        return {
            "choked": result["submodel"] == "choked_flow",
            "massFlowRate": result["release_rate_kg_s"],
            "sonicVelocity": round(sonic_velocity, 6),
        }

    @app.post("/source-models/gas-pipe")
    def source_gas_pipe_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            diameter = float(payload["pipeDiameter"])
            result = solve_source_model(
                "gas_release",
                {
                    "source_subtype": "pipe",
                    "pipe_diameter_m": diameter,
                    "pipe_area_m2": 3.141592653589793 * diameter**2 / 4.0,
                    "pipe_length_m": payload["pipeLength"],
                    "relative_roughness": float(payload["roughness"]) / max(diameter, 1e-9),
                    "upstream_pressure_pa": payload["upstreamPressure"],
                    "downstream_pressure_pa": payload["downstreamPressure"],
                    "temperature_k": payload["temperatureK"],
                    "molecular_weight_kg_kmol": payload["molecularWeight"],
                    "heat_capacity_ratio": payload.get("heatCapacityRatio", 1.3),
                    "duration_s": 1.0,
                    "inventory_mass_kg": 1e12,
                },
            )
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        gas_constant = get_constant_value("shared.universal_gas_constant") / (float(payload["molecularWeight"]) / 1000.0)
        sonic_velocity = (float(payload.get("heatCapacityRatio", 1.3)) * gas_constant * float(payload["temperatureK"])) ** 0.5
        return {
            "choked": result["submodel"] == "choked_flow",
            "massFlowRate": result["release_rate_kg_s"],
            "sonicVelocity": round(sonic_velocity, 6),
        }

    @app.post("/source-models/flashing-liquid")
    def source_flashing_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            material = get_material(str(payload["materialId"]))
            boiling_point_k = float(material.get("boilingPoint") or payload["initialTemperatureK"])
            total_mass = float(payload.get("inventoryMass", 1.0))
            result = solve_source_model(
                "flashing",
                {
                    "cp_liquid_j_kg_k": payload.get("cpLiquid", 2500.0),
                    "storage_temperature_k": payload["initialTemperatureK"],
                    "boiling_point_k": boiling_point_k,
                    "latent_heat_j_kg": payload.get("latentHeat", 300_000.0),
                    "total_mass_kg": total_mass,
                    "entrainment_fraction": payload.get("entrainmentFraction", 0.1),
                },
            )
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "vaporFraction": result["flash_fraction"],
            "liquidFraction": round(1.0 - float(result["flash_fraction"]), 6),
            "flashedMass": result["vapor_mass_kg"],
            "rainoutMass": result["rainout_mass_kg"],
        }

    @app.post("/source-models/scenario/select")
    def source_scenario_select_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return select_release_scenario(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/source-models/conservative-analysis")
    def source_conservative_analysis_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return apply_conservative_analysis(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dispersion/gaussian-plume")
    def gaussian_plume_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return run_gaussian_plume(payload)
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dispersion/gaussian-puff")
    def gaussian_puff_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return run_gaussian_puff(payload)
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dispersion/dense-gas")
    def dense_gas_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        request = dict(payload)
        try:
            if request.get("materialId") and request.get("gasDensityKgM3") is None:
                material = get_material(str(request["materialId"]))
                if material.get("density") is not None:
                    request["gasDensityKgM3"] = material["density"]
            return run_dense_gas(request)
        except (KeyError, ModelInputError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dispersion/isopleth")
    def isopleth_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return get_isopleth(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dispersion/toxic-endpoints/evaluate")
    def toxic_endpoints_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_toxic_endpoints(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/dispersion/prevention-mitigation")
    def dispersion_mitigation_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            scenario = dict(payload.get("scenario", {}))
            measures = [str(item) for item in payload.get("measures", [])]
            mitigation_factor = float(payload.get("mitigationFactor", min(0.8, 0.15 * len(measures))))
            return evaluate_release_mitigation(
                {
                    "releaseRate": scenario.get("releaseRate", scenario.get("release_rate", 1.0)),
                    "windSpeed": scenario.get("windSpeed", scenario.get("wind_speed", 3.0)),
                    "mitigationFactor": mitigation_factor,
                }
            )
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/flammability/mixture")
    def flammability_mixture_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_flammability_mixture(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/loc")
    def loc_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return calculate_loc(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/ignition-energy")
    def ignition_energy_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_ignition_energy(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/tnt-equivalency")
    def tnt_equivalency_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return calculate_tnt_equivalency(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/multi-energy")
    def multi_energy_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return calculate_multi_energy_blast(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/vce")
    def vce_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_vce(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/fire-explosion/bleve")
    def bleve_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return evaluate_bleve(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/prevention/inerting/purge")
    def inerting_purge_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return solve_purging_strategy(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/prevention/static-electricity/risk")
    def static_electricity_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return solve_static_electricity_risk(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/prevention/area-classification")
    def area_classification_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return solve_area_classification(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/prevention/fire-protection/strategy")
    def fire_protection_strategy_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return solve_fire_protection_strategy(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reactivity/calorimetry/interpret")
    def calorimetry_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return interpret_calorimetry(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reactivity/screening")
    def reactivity_screening_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return screen_reactivity(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/reactivity/control")
    def reactivity_control_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return recommend_reactivity_controls(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/devices/select")
    def relief_device_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return select_relief_device(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/system/analyze")
    def relief_system_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return analyze_relief_system(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/effluent-handling/select")
    def effluent_handling_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return select_effluent_handling(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/sizing/liquid")
    def relief_sizing_liquid_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return size_liquid_relief(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/sizing/gas-vapor")
    def relief_sizing_gas_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return size_gas_vapor_relief(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/sizing/two-phase")
    def relief_sizing_two_phase_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return size_two_phase_relief(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/sizing/deflagration-vent")
    def relief_sizing_deflagration_vent_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return size_deflagration_vent(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/sizing/external-fire")
    def relief_sizing_external_fire_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return size_external_fire_relief(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/relief/sizing/thermal-expansion")
    def relief_sizing_thermal_expansion_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return size_thermal_expansion_relief(payload)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/hazard-evaluation/checklist")
    def hazard_checklist_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_checklist(payload)

    @app.post("/hazard-evaluation/safety-review")
    def hazard_safety_review_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_safety_review(payload)

    @app.post("/hazard-evaluation/inherent-safety-review")
    def hazard_inherent_safety_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_inherent_safety_review(payload)

    @app.post("/hazard-evaluation/preliminary-hazard-analysis")
    def hazard_preliminary_analysis_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_preliminary_hazard_analysis(payload)

    @app.post("/hazard-evaluation/relative-ranking")
    def hazard_relative_ranking_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_relative_ranking(payload)

    @app.post("/hazard-evaluation/hazop")
    def hazard_hazop_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_hazop(payload)

    @app.post("/hazard-evaluation/fmea")
    def hazard_fmea_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_fmea(payload)

    @app.post("/hazard-evaluation/what-if")
    def hazard_what_if_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_what_if(payload)

    @app.post("/hazard-evaluation/what-if-checklist")
    def hazard_what_if_checklist_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return run_what_if(payload, checklist_items=[str(item) for item in payload.get("checklistItems", [])])

    @app.post("/hazard-evaluation/information-requirements/validate")
    def hazard_information_requirements_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
        return validate_information_requirements(payload)

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

    @app.post("/toxic-criteria/lookup", response_model=ServiceResponse)
    def lookup_toxic_criteria_endpoint(request: ServiceRequest) -> ServiceResponse:
        try:
            outputs = lookup_toxic_criteria(request.inputs)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _service_response("toxic_criteria_lookup", outputs, TOXIC_CRITERIA_METADATA)

    @app.post("/prevention-response-models/solve", response_model=ServiceResponse)
    def solve_prevention_response(request: ServiceRequest) -> ServiceResponse:
        try:
            outputs = solve_prevention_response_model(request.model_type, request.inputs)
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _service_response(request.model_type, outputs, PREVENTION_RESPONSE_METADATA)

    @app.post("/visualization/solve", response_model=VisualizationResponse)
    def solve_visualization(request: VisualizationRequest) -> VisualizationResponse:
        try:
            payload = build_visualization_layer(request.layer_type, request.inputs)
        except (ModelInputError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return VisualizationResponse(layer_type=request.layer_type, payload=payload)

    @app.post("/signs/analyze", response_model=SignAnalysisResponse)
    def analyze_sign_endpoint(request: SignAnalysisRequest) -> SignAnalysisResponse:
        try:
            payload = analyze_sign(request.model_dump(exclude_none=True))
        except ModelInputError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return SignAnalysisResponse(
            sign_type=str(payload["sign_type"]),
            confidence=float(payload["confidence"]),
            normalized_text=str(payload["normalized_text"]),
            matched_terms=[str(item) for item in payload.get("matched_terms", [])],
            asset_type=str(payload["asset_type"]),
            substance_family=str(payload["substance_family"]),
            hazard_classes=[str(item) for item in payload.get("hazard_classes", [])],
            recommended_services=[str(item) for item in payload.get("recommended_services", [])],
            recommended_models=dict(payload.get("recommended_models", {})),
            scenario_template_id=str(payload["scenario_template_id"]),
            scenario_definition_seed=dict(payload.get("scenario_definition_seed", {})),
            impact_zone_seed=dict(payload.get("impact_zone_seed", {})),
            required_parameters=[
                FieldMetadata(
                    name=str(item["name"]),
                    type=str(item["type"]),
                    description=str(item["description"]),
                    unit=str(item["unit"]) if item.get("unit") is not None else None,
                    required=True,
                    allowed_values=[],
                )
                for item in payload.get("required_parameters", [])
            ],
            notes=[str(item) for item in payload.get("notes", [])],
        )

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
