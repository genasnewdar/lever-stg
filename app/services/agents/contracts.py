from __future__ import annotations
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

# ---------- Input payload (matches your JSON) ----------

Question = List[Any]
SectionName = Literal["GRAMMAR", "VOCABULARY", "COMMUNICATION", "READING", "PART 2"]

class TestSection(BaseModel):
    section_name: SectionName
    questions: List[Question]

class TestPayload(BaseModel):
    student_name: str
    test_title: str
    score: float
    maximum_score: int
    time_taken_minutes: float
    sections: List[TestSection]

# ---------- Internal normalized models ----------

class SectionSlice(BaseModel):
    section_name: SectionName
    questions: List[Question]
    student_name: str

class QuestionInsight(BaseModel):
    index: int
    prompt: str
    student_answer: Optional[str] = None
    gold_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    gold_missing: bool = False
    reason_mn: Optional[str] = None
    skill_tag: Optional[str] = None
    priority: int = 2

class SectionInsights(BaseModel):
    name: SectionName
    summary_mn: str = ""
    accuracy: float = 0.0
    total: int = 0
    correct: int = 0
    questions: List[QuestionInsight] = Field(default_factory=list)

# ---------- Final API response ----------

class FinalReport(BaseModel):
    markdown: str
    sections: List[SectionInsights]
