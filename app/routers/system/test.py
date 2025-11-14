import logging
from fastapi import APIRouter, HTTPException, status, Request
from app.singleton import prisma
from datetime import datetime, timezone

router = APIRouter(prefix="/api/system/test")

# Set up logging (configure handlers/levels as needed)
logger = logging.getLogger("test")
logger.setLevel(logging.INFO)



# ----------------------------
# System End Student Test
# ----------------------------
@router.post("/finish")
async def system_finish_test(request: Request):
    try:
        print("====================== SYSTEM FINSIHED TEST ======================")
        body = await request.json()
        print(body)
        
        test_attempt_id = body.get("test_attempt_id")
        test_attempt = await prisma.testattempt.update(
            where={
                "id": test_attempt_id
            },
            data={
                "status": "SUBMITTED",
                "submitted_at": datetime.now(timezone.utc),
                "finish_id": "SYSTEM"
            }
        )
        print(test_attempt)
        ## insight
        return {"status": "success", "message": "Test finished successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error starting test: {str(e)}"
        )