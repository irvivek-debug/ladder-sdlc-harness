"""JSON schemas for model outputs — the subset both Gemini and Claude structured outputs accept
(every object closed with additionalProperties false and all properties required; no numeric/length limits)."""
from __future__ import annotations


def obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


S = {"type": "string"}
I = {"type": "integer"}

SUSPICIOUS = arr(obj({"where": S, "text": S, "why": S}))

EXPLAIN = obj({
    "device_comments": arr(obj({"device": S, "comment": S})),
    "rung_purposes": arr(obj({"rung": I, "purpose": S})),
    "suspicious": SUSPICIOUS,
})

EXTRACT = obj({
    "parameters": arr(obj({"name": S, "value": S, "units": S, "narrative_section": S})),
    "steps": arr(obj({"name": S, "entry": S, "exit": S})),
    "interlocks": arr(obj({"cause": S, "effect": S})),
    "alarms": arr(obj({"name": S, "condition": S, "action": S})),
    "conflicts": arr(obj({"item": S, "narrative_says": S, "parameter_sheet_says": S, "program_says": S,
                          "authoritative": S})),
})

CATEGORIES = ["double_coil", "timing", "missing_interlock", "semantic_logic", "documentation",
              "suspicious_instruction", "safety", "other"]

REVIEW = obj({
    "findings": arr(obj({
        "title": S,
        "category": {"type": "string", "enum": CATEGORIES},
        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
        "rungs": arr(I),
        "devices": arr(S),
        "evidence": S,
        "consequence": S,
        "proposed_fix": S,
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    })),
    "summary": S,
})

REPAIR = obj({
    "program_il": S,
    "change_summary": S,
    "changed_rungs": arr(I),
})
