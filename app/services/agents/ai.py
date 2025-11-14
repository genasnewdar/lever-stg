from __future__ import annotations
import json
import os
from typing import Any, Dict, List, Tuple

from .contracts import SectionSlice, SectionInsights, QuestionInsight
from .tools import normalize_prompt, safe_get

# ---- Swap-in: set your model names here ----
WORKER_MODEL = os.getenv("OBJ_WORKER_MODEL", "gpt-4o-mini")   # cheap worker
TEMP = float(os.getenv("OBJ_WORKER_TEMP", "0.1"))
MAX_TOKENS = int(os.getenv("OBJ_WORKER_MAXTOK", "1200"))

# ---- Choose one: OpenAI client (you can swap to Agents SDK) ----
try:
    from openai import OpenAI
    _client = OpenAI()
except Exception:
    _client = None

def _pack_questions(section: SectionSlice) -> List[Dict[str, Any]]:
    """
    Compress the raw array-ish question into a small dict the model can reason over.
    Your raw format:
      [0]=type, [1]=prompt, [2]=num?, [3]=choices[], [4]=correct, [5]=student (nullable)
    """
    items = []
    for i, q in enumerate(section.questions, start=1):
        qtype = safe_get(q, 0, "MULTIPLE_CHOICE")
        prompt = normalize_prompt(safe_get(q, 1, ""))
        choices = safe_get(q, 3, []) or []
        correct = safe_get(q, 4, None)
        student = safe_get(q, 5, None)
        items.append({
            "index": i,
            "type": qtype,
            "prompt": prompt,
            "choices": choices,           # keep for context, cheap tokens
            "correct_answer": correct,          # may be null
            "student_answer": student     # may be null
        })
    return items

def _system_prompt(section_name: str) -> str:
    return f"""
You are an EFL assessment assistant. Task: analyze one test section: {section_name}.
Rules:
- DO NOT invent correct answers. If correct_answer is null, set correct_missing=true and is_correct=null.
- Keep reasons SHORT (Mongolian), 1 sentence referencing the rule/idea.
- Choose ONE skill_tag per question
- priority: 1 if the learner was wrong; 2 otherwise.
Return STRICT JSON only in the specified schema. No extra text.
""".strip()

def _user_prompt(student_name: str, section_name: str, items: List[Dict[str, Any]]) -> str:
    payload = {
        "student_name": student_name,
        "section_name": section_name,
        "questions": items
    }
    return json.dumps(payload, ensure_ascii=False)

def _json_schema() -> Dict[str, Any]:
    # A tight schema to keep the response predictable
    return {
        "type": "object",
        "properties": {
            "summary_mn": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["index", "reason_mn", "skill_tag", "priority", "correct_missing"],
                    "properties": {
                        "index": {"type": "integer"},
                        "is_correct": {"type": ["boolean", "null"]},
                        "correct_missing": {"type": "boolean"},
                        "reason_mn": {"type": "string"},
                        "skill_tag": {"type": "string"},
                        "priority": {"type": "integer"},
                        "student_answer": {"type": ["string","null"]},
                        "correct_answer": {"type": ["string","null"]}
                    }
                }
            }
        },
        "required": ["summary_mn", "questions"]
    }

def _call_llm(system_prompt: str, user_json: str) -> Dict[str, Any]:
    """
    Calls the model in JSON mode. If your SDK doesn’t support JSON schema natively,
    ask for JSON and validate locally.
    """
    if _client is None:
        raise RuntimeError("OpenAI client is not available. Set OPENAI_API_KEY or install openai.")

    # Newer SDKs: responses.create with response_format={"type":"json_schema",...} — fallback to "json_object"
    try:
        resp = _client.responses.create(
            model=WORKER_MODEL,
            temperature=TEMP,
            max_output_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_json}
            ],
        )
        content = resp.output_text  # friendly accessor in new SDKs
    except Exception as e:
        # Fallback older chat.completions
        chat = _client.chat.completions.create(
            model=WORKER_MODEL,
            temperature=TEMP,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_json},
                {"role": "system", "content": "Return ONLY compact JSON with the required fields."}
            ],
        )
        content = chat.choices[0].message.content

    return json.loads(content)

def _recompute_and_validate(section: SectionSlice, raw_items: List[Dict[str, Any]], model_qs: List[Dict[str, Any]]) -> List[QuestionInsight]:
    """
    We never trust scoring blindly. If correct exists, recompute is_correct from student==correct.
    Also fill missing fields and keep everything consistent with your Pydantic model.
    """
    by_index = {it["index"]: it for it in raw_items}
    out: List[QuestionInsight] = []

    for q in model_qs:
        idx = int(q.get("index"))
        base = by_index.get(idx, {})
        correct = base.get("correct_answer")
        student = base.get("student_answer")

        correct_missing = correct is None
        # override model's is_correct with ground-truth comparison when possible
        is_correct = None if correct_missing else (student == correct)

        qi = QuestionInsight(
            index=idx,
            prompt=by_index.get(idx, {}).get("prompt", ""),
            student_answer=student,
            correct_answer=correct,
            is_correct=is_correct,
            correct_missing=correct_missing,
            reason_mn=q.get("reason_mn") or "Тайлбар дутуу.",
            skill_tag=q.get("skill_tag") or "General",
            priority=int(q.get("priority") or (1 if is_correct is False else 2))
        )
        out.append(qi)

    # Keep original ordering
    out.sort(key=lambda x: x.index)
    return out

def analyze_objective(section: SectionSlice, opts: Dict[str, Any]) -> SectionInsights:
    """
    LLM-backed worker. If anything goes wrong (e.g., JSON parse), we degrade gracefully.
    """
    items = _pack_questions(section)
    try:
        system_prompt = _system_prompt(section.section_name)
        user_json = _user_prompt(section.student_name, section.section_name, items)
        data = _call_llm(system_prompt, user_json)
        model_qs = data.get("questions", [])
        insights = _recompute_and_validate(section, items, model_qs)

        total = len(insights)
        correct = sum(1 for r in insights if r.is_correct is True)
        accuracy = round(correct / total, 4) if total else 0.0
        summary_mn = data.get("summary_mn") or f"{section.section_name} хэсгийн богино дүгнэлт."

        return SectionInsights(
            name=section.section_name,
            summary_mn=summary_mn,
            accuracy=accuracy,
            total=total,
            correct=correct,
            questions=insights
        )
    except Exception as e:
        # Graceful fallback: minimal heuristic (no crash)
        insights: List[QuestionInsight] = []
        for i, it in enumerate(items, start=1):
            correct_missing = it["correct_answer"] is None
            is_correct = None if correct_missing else (it["student_answer"] == it["correct_answer"])
            reason = "Автоматаар: зөв/бурууг шууд харьцуулсан."
            insights.append(QuestionInsight(
                index=i,
                prompt=it["prompt"],
                student_answer=it["student_answer"],
                correct_answer=it["correct_answer"],
                is_correct=is_correct,
                correct_missing=correct_missing,
                reason_mn=reason,
                skill_tag="General",
                priority=1 if is_correct is False else 2
            ))

        total = len(insights)
        correct = sum(1 for r in insights if r.is_correct is True)
        accuracy = round(correct / total, 4) if total else 0.0

        return SectionInsights(
            name=section.section_name,
            summary_mn=f"{section.section_name} хэсгийн дүгнэлт (fallback).",
            accuracy=accuracy,
            total=total,
            correct=correct,
            questions=insights
        )
