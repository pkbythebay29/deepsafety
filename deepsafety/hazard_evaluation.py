from __future__ import annotations

from typing import Any


def run_checklist(payload: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for item in payload.get("checklistItems", []):
        findings.append(
            {
                "nodeOrArea": payload.get("processId", "process"),
                "deviationOrIssue": str(item),
                "causes": ["Checklist item requires confirmation or evidence."],
                "consequences": ["Unknown until verified."],
                "safeguards": ["Existing procedures should be confirmed."],
                "recommendations": ["Document the response and close or escalate the checklist item."],
            }
        )
    return {"findings": findings}


def run_safety_review(payload: dict[str, Any]) -> dict[str, Any]:
    findings = [
        {
            "nodeOrArea": payload.get("processId", "process"),
            "deviationOrIssue": f"Safety review scope: {payload.get('scope', 'general')}",
            "causes": ["Formal review of scope, participants, and existing protections."],
            "consequences": ["Gaps can remain hidden without structured review."],
            "safeguards": ["Participant list and review scope."],
            "recommendations": ["Capture action items, owners, and due dates from the review."],
        }
    ]
    return {"findings": findings}


def run_inherent_safety_review(payload: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for strategy in payload.get("strategies", []):
        findings.append(
            {
                "nodeOrArea": payload.get("processId", "process"),
                "deviationOrIssue": f"Inherent safety strategy review: {strategy}",
                "causes": ["Process design may not yet apply the selected inherent safety principle."],
                "consequences": ["Hazards remain dependent on add-on safeguards."],
                "safeguards": ["Current design basis."],
                "recommendations": [f"Evaluate how to {strategy} the hazard at the source."],
            }
        )
    return {"findings": findings}


def run_preliminary_hazard_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for hazard in payload.get("hazards", []):
        findings.append(
            {
                "nodeOrArea": payload.get("processId", "process"),
                "deviationOrIssue": hazard,
                "causes": [str(item) for item in payload.get("causes", [])] or ["Cause not yet specified."],
                "consequences": ["Potential major process upset or release."],
                "safeguards": ["Preliminary review only."],
                "recommendations": ["Escalate significant hazards into a detailed hazard study."],
            }
        )
    return {"findings": findings}


def run_relative_ranking(payload: dict[str, Any]) -> dict[str, Any]:
    factors = dict(payload.get("factors", {}))
    score = sum(float(value) for value in factors.values() if isinstance(value, (int, float)))
    if score >= 20:
        rank_band = "very_high"
    elif score >= 12:
        rank_band = "high"
    elif score >= 6:
        rank_band = "moderate"
    else:
        rank_band = "low"
    return {"score": round(score, 6), "rankBand": rank_band}


def run_hazop(payload: dict[str, Any]) -> dict[str, Any]:
    findings = []
    guidewords = [str(item) for item in payload.get("guidewords", [])] or ["more", "less", "none"]
    for node in payload.get("nodes", []):
        for guideword in guidewords:
            findings.append(
                {
                    "nodeOrArea": str(node),
                    "deviationOrIssue": f"{guideword} than intended",
                    "causes": ["Loss of control, operator error, or equipment malfunction."],
                    "consequences": ["Process deviation could escalate to release, fire, or exposure."],
                    "safeguards": ["Instrumented alarms and operator response procedures."],
                    "recommendations": ["Verify safeguards and add recommendations where independence is weak."],
                }
            )
    return {"findings": findings}


def run_fmea(payload: dict[str, Any]) -> dict[str, Any]:
    findings = []
    for item in payload.get("equipmentItems", []):
        findings.append(
            {
                "nodeOrArea": str(item),
                "deviationOrIssue": "Failure mode review",
                "causes": ["Mechanical failure, corrosion, plugging, or instrument failure."],
                "consequences": ["Loss of containment or degraded protective function."],
                "safeguards": ["Inspection, maintenance, and protective instrumentation."],
                "recommendations": ["Rank severity and detectability, then assign follow-up actions."],
            }
        )
    return {"findings": findings}


def run_what_if(payload: dict[str, Any], checklist_items: list[str] | None = None) -> dict[str, Any]:
    findings = []
    prompts = [str(item) for item in payload.get("prompts", [])]
    if checklist_items:
        prompts.extend(checklist_items)
    for prompt in prompts:
        findings.append(
            {
                "nodeOrArea": payload.get("processId", "process"),
                "deviationOrIssue": prompt,
                "causes": ["What-if prompt raised for review."],
                "consequences": ["Outcome depends on safeguards and operating context."],
                "safeguards": ["Existing controls should be reviewed for this prompt."],
                "recommendations": ["Answer the prompt explicitly and assign actions if controls are weak."],
            }
        )
    return {"findings": findings}


def validate_information_requirements(payload: dict[str, Any]) -> dict[str, Any]:
    missing = []
    warnings = []
    chemicals = dict(payload.get("chemicals", {}))
    equipment = dict(payload.get("equipment", {}))
    procedures = dict(payload.get("procedures", {}))
    conditions = dict(payload.get("conditions", {}))

    if not chemicals:
        missing.append("chemical properties, flammability, toxicity, and reactivity data")
    else:
        for item in ["flammability", "toxicity", "reactivity", "physical_properties"]:
            if item not in chemicals:
                missing.append(f"chemicals.{item}")
    if not equipment:
        missing.append("equipment design data")
    if not procedures:
        missing.append("procedures")
    if not conditions:
        missing.append("operating conditions")
    else:
        for item in ["temperature", "pressure", "flow"]:
            if item not in conditions:
                warnings.append(f"conditions.{item} was not provided explicitly.")

    return {
        "complete": len(missing) == 0,
        "missingItems": missing,
        "warnings": warnings
        + [
            "Material data should be treated as foundational because source, dispersion, fire, and hazard studies all depend on it."
        ],
    }
