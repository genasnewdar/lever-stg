import logging
from fastapi import APIRouter, HTTPException, Security, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/admin/employee", tags=["Admin Employees"])
auth = VerifyToken()
logger = logging.getLogger("admin_employee")
logger.setLevel(logging.INFO)


class UserTypeEnum(str, Enum):
    STUDENT = "STUDENT"
    INSTRUCTOR = "INSTRUCTOR"
    ADMIN = "ADMIN"
    TEACHING_ASSISTANT = "TEACHING_ASSISTANT"


class EmployeeCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., max_length=255)
    auth0_id: Optional[str] = Field(None, description="Auth0 user id if known")
    type: Optional[UserTypeEnum] = Field(UserTypeEnum.ADMIN, description="Employee role type")


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    type: Optional[UserTypeEnum] = Field(None)


async def verify_admin_access(auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        requesting_user = await prisma.user.find_first(where={"auth0_id": user_id})

        if not requesting_user:
            logger.warning(f"User not found in database: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        if requesting_user.type != "ADMIN":
            logger.warning(
                f"Non-admin user attempted admin access: {user_id} (type: {requesting_user.type})"
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        return requesting_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying admin access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/list")
async def list_employees(
    admin_user = Depends(verify_admin_access),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, min_length=2, description="Search by name or email"),
    type: Optional[UserTypeEnum] = Query(None, description="Filter by employee type"),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    try:
        skip = (page - 1) * per_page
        filters: dict = {"is_deleted": False}

        if type:
            filters["type"] = type.value

        if search:
            filters["OR"] = [
                {"full_name": {"contains": search, "mode": "insensitive"}},
                {"email": {"contains": search, "mode": "insensitive"}},
            ]

        order_clause = {sort_by: sort_order}

        total = await prisma.employee.count(where=filters)
        employees = await prisma.employee.find_many(
            where=filters,
            skip=skip,
            take=per_page,
            order=order_clause,
            include={}
        )

        data = [
            {
                "id": e.id,
                "auth0_id": e.auth0_id,
                "full_name": e.full_name,
                "email": e.email,
                "type": e.type,
                "created_at": e.created_at,
                "updated_at": e.updated_at,
            }
            for e in employees
        ]

        logger.info(f"Admin {admin_user.auth0_id} listed employees page={page}")
        return {
            "status": "success",
            "data": {
                "employees": data,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page,
                    "has_next": page * per_page < total,
                    "has_previous": page > 1,
                },
            },
        }
    except Exception as e:
        logger.error(f"Error listing employees: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve employees")


@router.get("/{employee_id}")
async def get_employee(employee_id: int, admin_user = Depends(verify_admin_access)):
    try:
        employee = await prisma.employee.find_first(
            where={"id": employee_id, "is_deleted": False}
        )
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        return {"status": "success", "data": {"employee": employee}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting employee {employee_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve employee")


@router.post("")
async def create_employee(payload: EmployeeCreate, admin_user = Depends(verify_admin_access)):
    try:
        # Ensure no duplicate by email or auth0_id
        conflict = await prisma.employee.find_first(
            where={
                "OR": [
                    {"email": payload.email},
                    *( [{"auth0_id": payload.auth0_id}] if payload.auth0_id else [] )
                ]
            }
        )
        if conflict and not conflict.is_deleted:
            raise HTTPException(status_code=400, detail="Employee already exists")

        created = await prisma.employee.create(
            data={
                "full_name": payload.full_name,
                "email": payload.email,
                **({"auth0_id": payload.auth0_id} if payload.auth0_id else {}),
                **({"type": payload.type.value} if payload.type else {}),
            }
        )

        logger.info(f"Admin {admin_user.auth0_id} created employee {created.id}")
        return {"status": "success", "data": {"employee": created}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating employee: {e}")
        raise HTTPException(status_code=500, detail="Failed to create employee")


@router.put("/{employee_id}")
async def update_employee(employee_id: int, payload: EmployeeUpdate, admin_user = Depends(verify_admin_access)):
    try:
        employee = await prisma.employee.find_first(where={"id": employee_id, "is_deleted": False})
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        updated = await prisma.employee.update(
            where={"id": employee_id},
            data={
                **({"full_name": payload.full_name} if payload.full_name else {}),
                **({"email": payload.email} if payload.email else {}),
                **({"type": payload.type.value} if payload.type else {}),
                "updated_at": datetime.utcnow(),
            }
        )

        logger.info(f"Admin {admin_user.auth0_id} updated employee {employee_id}")
        return {"status": "success", "data": {"employee": updated}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating employee {employee_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update employee")


@router.delete("/{employee_id}")
async def delete_employee(employee_id: int, admin_user = Depends(verify_admin_access)):
    try:
        employee = await prisma.employee.find_first(where={"id": employee_id, "is_deleted": False})
        if not employee:
            return {"status": "success", "message": "Already deleted"}

        await prisma.employee.update(
            where={"id": employee_id},
            data={"is_deleted": True, "updated_at": datetime.utcnow()},
        )
        logger.info(f"Admin {admin_user.auth0_id} soft-deleted employee {employee_id}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error deleting employee {employee_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete employee")

