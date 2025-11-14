# app/services/agents/grader.py
from __future__ import annotations
from typing import List, Optional
from .contracts import TestPayload, SectionInsights, FinalReport
from .tools import mn_bool, md_answer

def _status_mn(score: float, max_score: float) -> str:
    pct = (score / max_score) if max_score else 0
    return "ГРАД" if pct >= 0.6 else "ТҮР ХҮЛЭЭГДЭЖ БАЙНА"

def _global_header(payload: TestPayload, sections: List[SectionInsights]) -> str:
    total = sum(s.total for s in sections)
    correct = sum(s.correct for s in sections)
    lines = []
    lines.append("# Шалгалтын Үр Дүнгийн Тайлан\n")
    lines.append("## Ерөнхий Мэдээлэл")
    lines.append(f"- **Оюутны Нэр:** {payload.student_name or 'Нэр дурдаагүй'}")
    lines.append(f"- **Шалгалтын Нэр:** {payload.test_title}")
    lines.append(f"- **Нийт Оноо:** {correct}/{total}")
    lines.append(f"- **Хугацаа:** {round(payload.time_taken_minutes) if payload.time_taken_minutes else 'Хугацаа дурдаагүй'}")
    lines.append(f"- **Төлөв:** {_status_mn(payload.score, payload.maximum_score)}\n")
    return "\n".join(lines)

def _section_details_block(sec: SectionInsights) -> str:
    lines = []
    lines.append(f"## {sec.name}")
    lines.append("\n## Асуулт Бүрийн Дэлгэрэнгүй Дүгнэлт\n")
    for r in sec.questions:
        lines.append(f"{r.index}. **{r.prompt}**")
        lines.append(f"   - **Зөв Хариулт:** {md_answer(r.gold_answer)}")
        lines.append(f"   - **Оюутны Хариулт:** {md_answer(r.student_answer)}")
        lines.append(f"   - **Тайлбар:** {r.reason_mn}\n")
    return "\n".join(lines)

def build_markdown(payload: TestPayload, sections: List[SectionInsights], supervisor_summary: Optional[str]) -> str:
    header = _global_header(payload, sections)
    per_section_blocks = [_section_details_block(s) for s in sections]
    blocks = [header]
    if supervisor_summary:
        blocks.append(supervisor_summary)
    blocks.extend(per_section_blocks)
    return "\n\n".join(blocks)

def finalize(payload: TestPayload, sections: List[SectionInsights], supervisor_summary: Optional[str] = None) -> FinalReport:
    md = build_markdown(payload, sections, supervisor_summary=supervisor_summary)
    return FinalReport(markdown=md, sections=sections)
