import logging
from fastapi import APIRouter, HTTPException, status, Request
from app.singleton import prisma
from datetime import datetime, timezone
import os

router = APIRouter(prefix="/api/user")
@router.get("/school/options")
async def get_school_options():
    try:
        schools = await prisma.school.find_many()
        return {
            "status": "success",
            "schools": [
                {"id": s.id, "name": s.name} for s in schools
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching schools: {e}")
        raise HTTPException(status_code=500, detail="FAILED_TO_FETCH_SCHOOLS")