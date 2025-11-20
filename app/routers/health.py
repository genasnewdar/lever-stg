from fastapi import APIRouter, Request, Depends, Security
# from app.utils import validate_api_key
from app.auth.auth import VerifyToken
from app.singleton import prisma
import time
from datetime import datetime

router = APIRouter(prefix="/api/health")
auth = VerifyToken()
start_time = time.time()


@router.get("")
async def health(auth_result: str = Security(auth.verify)):
    uptime = time.time() - start_time
    result = {
        "status": "OK",
        "uptime": round(uptime, 3),
        "date": datetime.now()
    }
    return result