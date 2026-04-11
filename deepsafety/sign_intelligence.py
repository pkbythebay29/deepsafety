from __future__ import annotations

import re
import unicodedata

from deepsafety.catalog import ModelInputError


SIGN_PATTERNS = {
    "gas_pipeline": {
        "keywords": [
            "gas pipeline",
            "gas line",
            "natural gas",
            "buried gas line",
            "pipeline gas",
            "gasleitung",
            "erdgas",
            "gasoducto",
            "tuberia de gas",
            "gazoduc",
            "gaz naturel",
            "gasleiding",
        ],
        "asset_type": "pipeline",
        "substance_family": "gas",
        "hazard_classes": ["release", "dispersion"],
        "recommended_incident_type": "pipe_rupture",
        "scenario_template_id": "pipeline_leak",
    },
    "high_pressure_gas": {
        "keywords": [
            "high pressure gas",
            "gas under pressure",
            "pressurized gas",
            "high pressure pipeline",
            "alta presion",
            "haute pression",
            "hoher druck",
        ],
        "asset_type": "pipeline",
        "substance_family": "pressurized_gas",
        "hazard_classes": ["release", "dispersion", "jet_fire"],
        "recommended_incident_type": "pipe_rupture",
        "scenario_template_id": "pipeline_leak",
    },
    "flammable_gas": {
        "keywords": [
            "flammable gas",
            "flammable",
            "extremely flammable",
            "inflammable gas",
            "gas inflamable",
            "gaz inflammable",
            "entzundliches gas",
            "lpg",
            "lng",
            "hydrogen",
        ],
        "asset_type": "gas_system",
        "substance_family": "flammable_gas",
        "hazard_classes": ["release", "dispersion", "jet_fire", "explosion"],
        "recommended_incident_type": "pipe_rupture",
        "scenario_template_id": "pipeline_leak",
    },
    "toxic_gas": {
        "keywords": [
            "toxic gas",
            "poison gas",
            "toxic inhalation",
            "chlorine",
            "ammonia",
            "h2s",
            "hydrogen sulfide",
            "gaz toxique",
            "gas toxico",
        ],
        "asset_type": "gas_system",
        "substance_family": "toxic_gas",
        "hazard_classes": ["release", "dispersion", "toxic_effects"],
        "recommended_incident_type": "pipe_rupture",
        "scenario_template_id": "toxic_gas_release",
    },
}

DEFAULT_REQUIRED_PARAMETERS = [
    {
        "name": "line_pressure_kpa",
        "type": "number",
        "description": "Internal line pressure at the sign location.",
        "unit": "kPa",
    },
    {
        "name": "gas_temperature_c",
        "type": "number",
        "description": "Gas temperature at release conditions.",
        "unit": "degC",
    },
    {
        "name": "diameter_m",
        "type": "number",
        "description": "Pipeline or nozzle diameter used for source-term calculations.",
        "unit": "m",
    },
    {
        "name": "hole_diameter_m",
        "type": "number",
        "description": "Estimated leak opening diameter.",
        "unit": "m",
    },
    {
        "name": "leak_duration_s",
        "type": "number",
        "description": "Estimated duration before isolation or depletion.",
        "unit": "s",
    },
    {
        "name": "stability_class",
        "type": "string",
        "description": "Pasquill stability class for dispersion screening.",
        "unit": None,
    },
    {
        "name": "wind_speed_m_s",
        "type": "number",
        "description": "Wind speed for dispersion screening.",
        "unit": "m/s",
    },
]


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9\s/.-]+", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def analyze_sign(payload: dict[str, object]) -> dict[str, object]:
    observed_text = str(payload.get("observed_text", "") or "").strip()
    image_base64 = str(payload.get("image_base64", "") or "").strip()
    site_context = str(payload.get("site_context", "") or "").strip()
    combined_text = " ".join(part for part in [observed_text, site_context] if part).strip()

    if not combined_text:
        if image_base64:
            raise ModelInputError(
                "A sign image was provided, but no extracted sign text was supplied. "
                "Pass OCR text in 'observed_text' or a manual text hint so the sign can be classified."
            )
        raise ModelInputError("Provide sign text in 'observed_text' or an OCR result to analyze the sign.")

    normalized_text = _normalize_text(combined_text)
    matches: list[dict[str, object]] = []
    for sign_type, pattern in SIGN_PATTERNS.items():
        matched_terms = [term for term in pattern["keywords"] if term in normalized_text]
        if matched_terms:
            score = len(matched_terms) / len(pattern["keywords"])
            matches.append(
                {
                    "sign_type": sign_type,
                    "matched_terms": matched_terms,
                    "score": score,
                    **pattern,
                }
            )

    if not matches:
        matches.append(
            {
                "sign_type": "unknown_gas_sign",
                "matched_terms": [],
                "score": 0.15 if "gas" in normalized_text or "pipeline" in normalized_text else 0.05,
                "asset_type": "pipeline" if "pipeline" in normalized_text or "line" in normalized_text else "gas_system",
                "substance_family": "gas",
                "hazard_classes": ["release", "dispersion"],
                "recommended_incident_type": "pipe_rupture",
                "scenario_template_id": "pipeline_leak",
            }
        )

    best_match = max(matches, key=lambda item: float(item["score"]))
    hazard_classes = list(dict.fromkeys(best_match["hazard_classes"]))

    recommended_services = ["scenario_engine", "source_models", "dispersion_models", "visualization"]
    if "jet_fire" in hazard_classes or "explosion" in hazard_classes:
        recommended_services.append("fire_explosion_models")
    if "toxic_effects" in hazard_classes or "explosion" in hazard_classes or "jet_fire" in hazard_classes:
        recommended_services.append("effect_models")

    recommended_models = {
        "source_model": "gas_release",
        "dispersion_model": "gaussian_puff",
        "impact_endpoint": "/gis/impact-zones",
        "scenario_endpoint": "/scenario-engine/define",
    }
    if "jet_fire" in hazard_classes:
        recommended_models["fire_model"] = "jet_fire"
    if "explosion" in hazard_classes:
        recommended_models["explosion_model"] = "vce"
    if "toxic_effects" in hazard_classes:
        recommended_models["effect_model"] = "toxic_probit"

    return {
        "sign_type": best_match["sign_type"],
        "confidence": round(float(best_match["score"]), 6),
        "normalized_text": normalized_text,
        "matched_terms": best_match["matched_terms"],
        "asset_type": best_match["asset_type"],
        "substance_family": best_match["substance_family"],
        "hazard_classes": hazard_classes,
        "recommended_services": recommended_services,
        "recommended_models": recommended_models,
        "scenario_template_id": best_match["scenario_template_id"],
        "scenario_definition_seed": {
            "incident_type": best_match["recommended_incident_type"],
            "classification": "realistic_case",
            "inventory": {"phase": "gas"},
            "equipment": {"type": best_match["asset_type"]},
            "failure_mode": "leak",
            "topography": payload.get("topography", "urban"),
        },
        "impact_zone_seed": {
            "scenario_type": "leak",
            "asset": {
                "stability_class": payload.get("stability_class", "D"),
                "wind_speed_m_s": payload.get("wind_speed_m_s", 3.0),
                "gas_temperature_c": None,
                "line_pressure_kpa": None,
                "diameter_m": None,
                "hole_diameter_m": None,
                "leak_duration_s": 300.0,
            },
            "criteria": [
                {
                    "label": "Concern threshold",
                    "threshold": 0.02,
                    "unit": "kg/m^3",
                }
            ],
        },
        "required_parameters": DEFAULT_REQUIRED_PARAMETERS,
        "notes": [
            "This endpoint classifies the sign from extracted or manually entered text.",
            "For image-based workflows, run OCR first and pass the extracted text through 'observed_text'.",
            "The returned scenario seeds can be sent directly into the Deep Safety scenario and impact endpoints.",
        ],
    }
