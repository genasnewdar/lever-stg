import logging
from fastapi import APIRouter, HTTPException, Security, Query, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from enum import Enum
from datetime import datetime

from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/admin/user", tags=["Admin Users"])
auth = VerifyToken()
logger = logging.getLogger("admin_user")
logger.setLevel(logging.INFO)

# Enum for user types (should match your Prisma schema)
class UserTypeEnum(str, Enum):
    STUDENT = "STUDENT"
    INSTRUCTOR = "INSTRUCTOR"
    ADMIN = "ADMIN"
    TEACHING_ASSISTANT = "TEACHING_ASSISTANT"

# Pydantic models for request validation
class UpdateUserRoleRequest(BaseModel):
    user_id: str = Field(..., description="Auth0 ID of the user to update")
    new_role: UserTypeEnum = Field(..., description="New role to assign")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for role change")

class BulkRoleUpdateRequest(BaseModel):
    user_ids: List[str] = Field(..., min_items=1, max_items=50, description="List of user Auth0 IDs")
    new_role: UserTypeEnum = Field(..., description="New role to assign to all users")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for bulk role change")

# Dependency to verify admin access
async def verify_admin_access(auth_result: str = Security(auth.verify)):
    """Verify that the requesting user has admin privileges"""
    try:
        user_id = auth_result["sub"]
        requesting_user = await prisma.user.find_first(where={"auth0_id": user_id})
        
        if not requesting_user:
            logger.warning(f"User not found in database: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        if requesting_user.type != "ADMIN":
            logger.warning(f"Non-admin user attempted admin access: {user_id} (type: {requesting_user.type})")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        return requesting_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying admin access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/list")
async def list_users(
    admin_user = Depends(verify_admin_access),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, min_length=2, description="Search term for name, email, or phone"),
    user_type: Optional[UserTypeEnum] = Query(None, description="Filter by user type"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order")
):
    """List users with filtering, searching, and pagination"""
    try:
        skip = (page - 1) * per_page
        filters = {"is_deleted": False}
        
        # Add user type filter
        if user_type:
            filters["type"] = user_type.value
        
        # Add search filter
        if search:
            filters["OR"] = [
                {"full_name": {"contains": search, "mode": "insensitive"}},
                {"email": {"contains": search, "mode": "insensitive"}},
                {"phone": {"contains": search, "mode": "insensitive"}},
            ]
        
        # Build order clause
        order_clause = {sort_by: sort_order}
        
        # Get total count and users
        total_count = await prisma.user.count(where=filters)
        users = await prisma.user.find_many(
            where=filters,
            skip=skip,
            take=per_page,
            order=order_clause,
            include={
                "school_class": {
                    "include": {"school": True}
                },
                # "enrollments": {"select": {"id": True}},
                # "instructor_courses": {"select": {"id": True}},
            }
        )
        
        # Format user data
        user_list = []
        for user in users:
            user_data = {
                "id": user.id,
                "auth0_id": user.auth0_id,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "type": user.type,
                "picture": user.picture,
                "bio": user.bio,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "login_count": user.login_count,
                "school_info": None,
                "stats": {
                    "enrollments_count": len(user.enrollments),
                    "instructor_courses_count": len(user.instructor_courses),
                }
            }
            
            # Add school information if available
            if user.school_class:
                user_data["school_info"] = {
                    "class_name": user.school_class.name,
                    "school_name": user.school_class.school.name if user.school_class.school else None
                }
            
            user_list.append(user_data)
        
        logger.info(f"Admin {admin_user.auth0_id} listed users: page={page}, filters={filters}")
        
        return {
            "status": "success",
            "data": {
                "users": user_list,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total_count,
                    "total_pages": (total_count + per_page - 1) // per_page,
                    "has_next": page * per_page < total_count,
                    "has_previous": page > 1
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve users")

@router.get("/{user_id}")
async def get_user_details(
    user_id: str,
    admin_user = Depends(verify_admin_access)
):
    """Get detailed information about a specific user"""
    try:
        user = await prisma.user.find_first(
            where={"auth0_id": user_id, "is_deleted": False},
            include={
                "school_class": {
                    "include": {"school": True}
                },
                "enrollments": {
                    "include": {"course": {"select": {"title": True, "id": True}}}
                },
                "instructor_courses": {
                    "select": {"id": True, "title": True, "enrollment_count": True}
                },
                "created_courses": {
                    "select": {"id": True, "title": True}
                },
                "course_reviews": {
                    "select": {"rating": True, "course": {"select": {"title": True}}}
                }
            }
        )
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Calculate additional stats
        avg_rating = 0
        if user.course_reviews:
            avg_rating = sum(review.rating for review in user.course_reviews) / len(user.course_reviews)
        
        user_details = {
            "id": user.id,
            "auth0_id": user.auth0_id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "type": user.type,
            "picture": user.picture,
            "bio": user.bio,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "login_count": user.login_count,
            "school_info": None,
            "stats": {
                "enrollments_count": len(user.enrollments),
                "instructor_courses_count": len(user.instructor_courses),
                "created_courses_count": len(user.created_courses),
                "reviews_count": len(user.course_reviews),
                "average_rating_given": round(avg_rating, 2) if avg_rating else None
            },
            "enrollments": [
                {
                    "course_id": enrollment.course.id,
                    "course_title": enrollment.course.title,
                    "enrolled_at": enrollment.enrolled_at,
                    "status": enrollment.status,
                    "progress": enrollment.progress_percentage
                }
                for enrollment in user.enrollments
            ]
        }
        
        # Add school information
        if user.school_class:
            user_details["school_info"] = {
                "class_id": user.school_class.id,
                "class_name": user.school_class.name,
                "school_id": user.school_class.school.id if user.school_class.school else None,
                "school_name": user.school_class.school.name if user.school_class.school else None
            }
        
        logger.info(f"Admin {admin_user.auth0_id} viewed user details: {user_id}")
        return {"status": "success", "data": {"user": user_details}}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user details for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user details")

@router.put("/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    admin_user = Depends(verify_admin_access)
):
    """Update a user's role (promote/demote)"""
    try:
        # Validate that the user_id in path matches the one in request body
        if user_id != request.user_id:
            raise HTTPException(status_code=400, detail="User ID mismatch between path and request body")
        
        # Prevent admin from changing their own role
        if user_id == admin_user.auth0_id:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        
        # Find the target user
        target_user = await prisma.user.find_first(
            where={"auth0_id": user_id, "is_deleted": False}
        )
        
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Store the old role for logging
        old_role = target_user.type
        
        # Check if role is actually changing
        if old_role == request.new_role.value:
            return {
                "status": "success",
                "message": f"User already has role {request.new_role.value}",
                "data": {"user_id": user_id, "role": request.new_role.value}
            }
        
        # Update the user's role
        updated_user = await prisma.user.update(
            where={"auth0_id": user_id},
            data={
                "type": request.new_role.value,
                "updated_at": datetime.utcnow()
            }
        )
        
        # Log the role change
        log_message = (
            # f"Admin {admin_user.auth0_id} ({admin_user.full_name}) changed role for user "
            f"{user_id} ({target_user.full_name}) from {old_role} to {request.new_role.value}"
        )
        if request.reason:
            log_message += f". Reason: {request.reason}"
        
        logger.info(log_message)
        
        return {
            "status": "success",
            "message": f"User role updated from {old_role} to {request.new_role.value}",
            "data": {
                "user_id": user_id,
                "old_role": old_role,
                "new_role": request.new_role.value,
                "updated_at": updated_user.updated_at
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user role")

@router.put("/bulk/role")
async def bulk_update_user_roles(
    request: BulkRoleUpdateRequest,
    admin_user = Depends(verify_admin_access)
):
    """Update multiple users' roles in bulk"""
    try:
        # Prevent admin from changing their own role
        if admin_user.auth0_id in request.user_ids:
            raise HTTPException(status_code=400, detail="Cannot change your own role in bulk operation")
        
        # Find all target users
        target_users = await prisma.user.find_many(
            where={
                "auth0_id": {"in": request.user_ids},
                "is_deleted": False
            }
        )
        
        if len(target_users) != len(request.user_ids):
            found_ids = {user.auth0_id for user in target_users}
            missing_ids = set(request.user_ids) - found_ids
            raise HTTPException(
                status_code=404,
                detail=f"Some users not found: {list(missing_ids)}"
            )
        
        # Track changes
        changes = []
        unchanged = []
        
        # Update each user's role
        for user in target_users:
            if user.type == request.new_role.value:
                unchanged.append({
                    "user_id": user.auth0_id,
                    "full_name": user.full_name,
                    "role": user.type
                })
            else:
                old_role = user.type
                await prisma.user.update(
                    where={"auth0_id": user.auth0_id},
                    data={
                        "type": request.new_role.value,
                        "updated_at": datetime.utcnow()
                    }
                )
                changes.append({
                    "user_id": user.auth0_id,
                    "full_name": user.full_name,
                    "old_role": old_role,
                    "new_role": request.new_role.value
                })
        
        # Log the bulk change
        log_message = (
            f"Admin {admin_user.auth0_id} ({admin_user.full_name}) performed bulk role update: "
            f"{len(changes)} users changed to {request.new_role.value}, {len(unchanged)} unchanged"
        )
        if request.reason:
            log_message += f". Reason: {request.reason}"
        
        logger.info(log_message)
        
        return {
            "status": "success",
            "message": f"Bulk role update completed: {len(changes)} changed, {len(unchanged)} unchanged",
            "data": {
                "changes": changes,
                "unchanged": unchanged,
                "new_role": request.new_role.value
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk role update: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user roles")

@router.get("/stats/roles")
async def get_user_role_statistics(
    admin_user = Depends(verify_admin_access)
):
    """Get statistics about user roles distribution"""
    try:
        # Get role counts
        role_stats = await prisma.user.group_by(
            by=["type"],
            where={"is_deleted": False},
            _count=True
        )
        
        # Get total user count
        total_users = await prisma.user.count(where={"is_deleted": False})
        
        # Format the statistics
        role_distribution = {}
        for stat in role_stats:
            role_distribution[stat["type"]] = {
                "count": stat["_count"],
                "percentage": round((stat["_count"] / total_users) * 100, 2) if total_users > 0 else 0
            }
        
        # Ensure all role types are represented
        for role in UserTypeEnum:
            if role.value not in role_distribution:
                role_distribution[role.value] = {"count": 0, "percentage": 0}
        
        logger.info(f"Admin {admin_user.auth0_id} viewed role statistics")
        
        return {
            "status": "success",
            "data": {
                "total_users": total_users,
                "role_distribution": role_distribution,
                "generated_at": datetime.utcnow()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting role statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve role statistics")