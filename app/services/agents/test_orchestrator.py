import json
import asyncio
from .contracts import InputPayload
from .orchestrator import run_feedback_pipeline
from .registry import register_worker
from .ai import analyze_section_objective

# register workers for tests/runtime
register_worker("objective", analyze_section_objective)

async def main():
    with open("services/agents/cleaned_payload.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    payload = InputPayload(**data)
    report = await run_feedback_pipeline(payload)
    print(report.markdown[:2000])  # preview

if __name__ == "__main__":
    asyncio.run(main())
