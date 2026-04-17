from __future__ import annotations
import json
import os

from openai import AsyncOpenAI

from .rubrics import CR_SECTIONS, CS_SECTIONS, CR_RUBRIC, CS_RUBRIC, CR_MAX, CS_MAX, CR_PASS, CS_PASS

_SYSTEM = (
    "You are an expert ABVP credentialing reviewer with extensive experience evaluating "
    "veterinary Case Summaries (CS) and Case Reports (CR). Apply the official ABVP rubric "
    "precisely and consistently. Provide constructive, specific feedback to help applicants "
    "improve. Respond ONLY with valid JSON."
)


def _client() -> AsyncOpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return AsyncOpenAI(api_key=key)


async def run_ai_review(submission_type: str, document_text: str) -> dict:
    is_cs = submission_type == "case_summary"
    sections = CS_SECTIONS if is_cs else CR_SECTIONS
    rubric = CS_RUBRIC if is_cs else CR_RUBRIC
    max_score = CS_MAX if is_cs else CR_MAX
    pass_score = CS_PASS if is_cs else CR_PASS
    doc_label = "Case Summary" if is_cs else "Case Report"
    wc_rule = "Word count must be 1,700-2,000 words" if is_cs else "Word count must not exceed 19,000 words"

    section_json = ",\n    ".join(
        f'"{s["key"]}": {{"score": 0, "rationale": "..."}}'
        for s in sections
    )

    prompt = f"""You are reviewing a veterinary {doc_label} submission for ABVP credentialing.

RUBRIC:
{rubric}

SUBMISSION TEXT:
---
{document_text[:14000]}{"\\n[... text truncated ...]" if len(document_text) > 14000 else ""}
---

Respond with ONLY a valid JSON object with this exact structure:
{{
  "submission_type": "{submission_type}",
  "section_scores": {{
    {section_json}
  }},
  "overall_impression_a": {{"pass": true, "rationale": "..."}},
  "overall_impression_b": {{"pass": true, "rationale": "..."}},
  "word_count_estimate": 0,
  "word_count_pass": true,
  "word_count_note": "{wc_rule}",
  "formatting_deductions": 0,
  "formatting_notes": [],
  "estimated_total": 0,
  "estimated_max": {max_score},
  "estimated_pass_score": {pass_score},
  "estimated_pct": 0.0,
  "estimated_pass": false,
  "auto_fail_reasons": [],
  "flags": [],
  "strengths": [],
  "weaknesses": []
}}

Rules:
- Score each section 0-4 using the rubric criteria above
- estimated_total = sum of (score * max_pts / 4) for each section minus formatting_deductions
- estimated_pct = (estimated_total / {max_score}) * 100
- estimated_pass = true only if estimated_pct >= 70 AND no section scored 0 AND both overall impressions passed AND word_count_pass is true
- auto_fail_reasons: list any "Section scored 0: [name]", "Overall Impression A failed", "Overall Impression B failed", "Word count out of range"
- Provide 3-5 specific, actionable strengths and 3-5 specific, actionable areas for improvement in weaknesses
"""

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    client = _client()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)
