# app/routers/system/agent_feedback.py
from fastapi import APIRouter
from app.services.agents.contracts import TestPayload, FinalReport
from app.services.agents.orchestrator import Orchestrator

router = APIRouter(prefix="/agents", tags=["agents"])
orc = Orchestrator()

@router.post("/analyze", response_model=FinalReport)
def analyze(payload: TestPayload):
    test = orc.ingest(payload.model_dump())
    insights = orc.analyze_sections(test)
    rubric = orc.grade_with_rubric(test, insights)
    return orc.merge_and_polish(test, insights, rubric)
