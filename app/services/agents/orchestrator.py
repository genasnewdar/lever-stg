# app/services/agents/orchestrator.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple
import asyncio
from collections import Counter

from .contracts import TestPayload, SectionSlice, SectionInsights, FinalReport
from .agent_feedback import route
from .registry import get_worker, register_worker
from .ai import analyze_objective
from .grader import finalize  # we'll pass a supervisor_summary into finalize

class Orchestrator:
    def __init__(self) -> None:
        try:
            get_worker("objective")
        except KeyError:
            register_worker("objective", analyze_objective)

    def ingest(self, raw: Dict[str, Any]) -> TestPayload:
        return TestPayload(**raw)

    def _section_tasks(self, test: TestPayload) -> List[asyncio.Task]:
        async def run_one(slice_: SectionSlice) -> SectionInsights:
            key, cfg = route(slice_)
            worker = get_worker(key)["fn"]
            return await asyncio.to_thread(worker, slice_, cfg)

        tasks: List[asyncio.Task] = []
        for s in test.sections:
            slice_ = SectionSlice(
                section_name=s.section_name,
                questions=s.questions,
                student_name=test.student_name,
            )
            tasks.append(asyncio.create_task(run_one(slice_)))
        return tasks

    def analyze_sections(self, test: TestPayload) -> List[SectionInsights]:
        async def _go():
            return await asyncio.gather(*self._section_tasks(test))
        return asyncio.run(_go())

    def grade_with_rubric(self, test: TestPayload, insights: List[SectionInsights]) -> Dict[str, Any]:
        return {"version": "v2", "notes": "supervisor summary produced in orchestrator"}

    # ---- Supervisor logic lives here now ----
    def _aggregate(self, insights: List[SectionInsights]) -> Tuple[int, int, float, Counter]:
        total = sum(s.total for s in insights)
        correct = sum(s.correct for s in insights)
        acc = round((correct / total) if total else 0.0, 4)
        skills = Counter()
        for s in insights:
            for q in s.questions:
                if q.is_correct is False and q.skill_tag:
                    skills[q.skill_tag] += 1
        return total, correct, acc, skills

    def build_supervisor_summary(self, payload: TestPayload, insights: List[SectionInsights]) -> str:
        total, correct, acc, skills = self._aggregate(insights)
        pct = int(acc * 100)
        top3 = [f"- **{name}** ({count} алдаа)" for name, count in skills.most_common(3)] \
               or ["- Давтамжтай алдаа тодорхойлоход мэдээлэл дутуу."]

        lines: List[str] = []
        lines.append("## Ерөнхий Дүгнэлт (Монгол хэлээр)")
        lines.append(
            f"Энэхүү шалгалтад нийт **{total}** асуултаас **{correct}** зөв хариулж, амжилтын түвшин **{pct}%** байна. "
            "Суралцагчийн ахиц дэвшлийг нэмэгдүүлэхийн тулд доорх ур чадваруудад зорилтот давтлага хийхийг зөвлөж байна."
        )
        lines.append("\n### Давтамжтай алдааны чиглэлүүд")
        lines.extend(top3)

        lines.append("\n### Богино хугацааны төлөвлөгөө")
        lines.append("- **Өдөр бүр 20–30 мин:** зорилтот дүрмийн/лексикийн drills")
        lines.append("- **Долоо хоногт 2 удаа:** шинэ сэдвийн жишээ өгүүлбэр бичих ба өөрөө шалгах")
        lines.append("- **Давтлага:** буруу хариулсан асуулт бүр дээр дүрэм/тайлбарыг дахин үзэх")
        return "\n".join(lines)
    # -----------------------------------------

    def merge_and_polish(self, test: TestPayload, insights: List[SectionInsights], rubric: Dict[str, Any]) -> FinalReport:
        supervisor_summary = self.build_supervisor_summary(test, insights)
        return finalize(test, insights, supervisor_summary=supervisor_summary)
