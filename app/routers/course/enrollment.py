import time
import logging
from fastapi import APIRouter, HTTPException, Security, status, Query
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/course")
auth = VerifyToken()
start_time = time.time()

# Set up logging
logger = logging.getLogger("course_enrollment")
logger.setLevel(logging.INFO)

# Pydantic models
class EnrollmentCreate(BaseModel):
    course_id: str

class EnrollmentResponse(BaseModel):
    id: str
    course_id: str
    course_title: str
    status: str
    enrolled_at: datetime
    completed_at: Optional[datetime] = None
    progress_percentage: float
    last_accessed_at: Optional[datetime] = None

class EnrollmentUpdate(BaseModel):
    status: str  # ACTIVE, COMPLETED, DROPPED, SUSPENDED

# ----------------------------
# Enroll in Course
# ----------------------------
@router.post("/enroll")
async def enroll_in_course(
    enrollment_data: EnrollmentCreate,
    auth_result: str = Security(auth.verify)
):
    """Enroll the current user in a course"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and is published
        course = await prisma.course.find_first(
            where={
                "id": enrollment_data.course_id,
                "is_published": True
            }
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Check if user is already enrolled
        existing_enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": enrollment_data.course_id
            }
        )
        
        if existing_enrollment:
            raise Exception("USER_ALREADY_ENROLLED")
        
        # Create new enrollment
        new_enrollment = await prisma.enrollment.create(
            data={
                "user_id": user.auth0_id,
                "course_id": enrollment_data.course_id,
                "status": "ACTIVE",
                "enrolled_at": datetime.now(timezone.utc)
            }
        )
        
        # Update course enrollment count
        await prisma.course.update(
            where={"id": enrollment_data.course_id},
            data={"enrollment_count": {"increment": 1}}
        )
        
        return {
            "status": "success",
            "enrollment": {
                "id": new_enrollment.id,
                "course_id": new_enrollment.course_id,
                "course_title": course.title,
                "status": new_enrollment.status,
                "enrolled_at": new_enrollment.enrolled_at,
                "completed_at": new_enrollment.completed_at,
                "progress_percentage": new_enrollment.progress_percentage,
                "last_accessed_at": new_enrollment.last_accessed_at
            }
        }
        
    except Exception as e:
        logger.error(f"Error enrolling in course: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get My Enrollments
# ----------------------------
@router.get("/my-enrollments")
async def get_my_enrollments(
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None)
):
    """Get all enrollments for the current user"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        skip = (page - 1) * per_page
        
        # Build where clause
        where_clause = {"user_id": user.auth0_id}
        if status_filter:
            where_clause["status"] = status_filter
        
        total_count = await prisma.enrollment.count(where=where_clause)
        
        enrollments = await prisma.enrollment.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order={"enrolled_at": "desc"},
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "short_title": True,
                        "thumbnail_url": True,
                        "difficulty_level": True,
                        "estimated_duration": True,
                        "category": True,
                        "rating": True,
                        "instructor": {
                            "select": {
                                "auth0_id": True,
                                "full_name": True,
                                "picture": True
                            }
                        }
                    }
                }
            }
        )
        
        formatted_enrollments = []
        for enrollment in enrollments:
            course = enrollment.course
            formatted_enrollments.append({
                "id": enrollment.id,
                "course_id": enrollment.course_id,
                "course": {
                    "id": course.id,
                    "title": course.title,
                    "short_title": course.short_title,
                    "thumbnail_url": course.thumbnail_url,
                    "difficulty_level": course.difficulty_level,
                    "estimated_duration": course.estimated_duration,
                    "category": course.category,
                    "rating": course.rating,
                    "instructor": course.instructor
                },
                "status": enrollment.status,
                "enrolled_at": enrollment.enrolled_at,
                "completed_at": enrollment.completed_at,
                "progress_percentage": enrollment.progress_percentage,
                "last_accessed_at": enrollment.last_accessed_at
            })
        
        return {
            "status": "success",
            "enrollments": formatted_enrollments,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching user enrollments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Enrollment Status for Specific Course
# ----------------------------
@router.get("/{course_id}/enrollment")
async def get_enrollment_status(
    course_id: str,
    auth_result: str = Security(auth.verify)
):
    """Get enrollment status for a specific course"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id
            },
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "short_title": True,
                        "is_published": True
                    }
                }
            }
        )
        
        if not enrollment:
            # Check if course exists
            course = await prisma.course.find_first(
                where={"id": course_id, "is_published": True}
            )
            if not course:
                raise Exception("COURSE_NOT_FOUND")
            
            return {
                "status": "success",
                "enrolled": False,
                "course_id": course_id,
                "course_title": course.title
            }
        
        return {
            "status": "success",
            "enrolled": True,
            "enrollment": {
                "id": enrollment.id,
                "course_id": enrollment.course_id,
                "course_title": enrollment.course.title,
                "status": enrollment.status,
                "enrolled_at": enrollment.enrolled_at,
                "completed_at": enrollment.completed_at,
                "progress_percentage": enrollment.progress_percentage,
                "last_accessed_at": enrollment.last_accessed_at
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking enrollment status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Update Enrollment Status
# ----------------------------
@router.put("/{course_id}/enrollment")
async def update_enrollment(
    course_id: str,
    enrollment_update: EnrollmentUpdate,
    auth_result: str = Security(auth.verify)
):
    """Update enrollment status (e.g., drop course, complete course)"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id
            },
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True
                    }
                }
            }
        )
        
        if not enrollment:
            raise Exception("ENROLLMENT_NOT_FOUND")
        
        # Prepare update data
        update_data = {"status": enrollment_update.status}
        
        # Set completion date if status is COMPLETED
        if enrollment_update.status == "COMPLETED":
            update_data["completed_at"] = datetime.now(timezone.utc)
            update_data["progress_percentage"] = 100.0
        
        # Update enrollment
        updated_enrollment = await prisma.enrollment.update(
            where={"id": enrollment.id},
            data=update_data
        )
        
        return {
            "status": "success",
            "enrollment": {
                "id": updated_enrollment.id,
                "course_id": updated_enrollment.course_id,
                "course_title": enrollment.course.title,
                "status": updated_enrollment.status,
                "enrolled_at": updated_enrollment.enrolled_at,
                "completed_at": updated_enrollment.completed_at,
                "progress_percentage": updated_enrollment.progress_percentage,
                "last_accessed_at": updated_enrollment.last_accessed_at
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating enrollment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Withdraw from Course
# ----------------------------
@router.delete("/{course_id}/enrollment")
async def withdraw_from_course(
    course_id: str,
    auth_result: str = Security(auth.verify)
):
    """Withdraw from a course (soft delete by changing status to DROPPED)"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id
            }
        )
        
        if not enrollment:
            raise Exception("ENROLLMENT_NOT_FOUND")
        
        if enrollment.status == "DROPPED":
            raise Exception("ALREADY_WITHDRAWN")
        
        # Update enrollment status to DROPPED
        await prisma.enrollment.update(
            where={"id": enrollment.id},
            data={"status": "DROPPED"}
        )
        
        # Update course enrollment count (decrement)
        course = await prisma.course.find_first(
            where={"id": course_id}
        )
        if course and course.enrollment_count > 0:
            await prisma.course.update(
                where={"id": course_id},
                data={"enrollment_count": {"decrement": 1}}
            )
        
        return {
            "status": "success",
            "message": "Successfully withdrawn from course"
        }
        
    except Exception as e:
        logger.error(f"Error withdrawing from course: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Enrollment Statistics for User
# ----------------------------
@router.get("/enrollment/stats")
async def get_enrollment_stats(
    auth_result: str = Security(auth.verify)
):
    """Get enrollment statistics for the current user"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Count enrollments by status
        active_count = await prisma.enrollment.count(
            where={"user_id": user.auth0_id, "status": "ACTIVE"}
        )
        
        completed_count = await prisma.enrollment.count(
            where={"user_id": user.auth0_id, "status": "COMPLETED"}
        )
        
        dropped_count = await prisma.enrollment.count(
            where={"user_id": user.auth0_id, "status": "DROPPED"}
        )
        
        total_enrollments = active_count + completed_count + dropped_count
        
        # Get recently enrolled courses (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=30)
        
        recent_enrollments = await prisma.enrollment.count(
            where={
                "user_id": user.auth0_id,
                "enrolled_at": {"gte": thirty_days_ago}
            }
        )
        
        # Calculate average progress for active courses
        active_enrollments = await prisma.enrollment.find_many(
            where={"user_id": user.auth0_id, "status": "ACTIVE"},
            select={"progress_percentage": True}
        )
        
        avg_progress = 0
        if active_enrollments:
            total_progress = sum(e.progress_percentage for e in active_enrollments)
            avg_progress = round(total_progress / len(active_enrollments), 1)
        
        return {
            "status": "success",
            "enrollment_stats": {
                "total_enrollments": total_enrollments,
                "active_courses": active_count,
                "completed_courses": completed_count,
                "dropped_courses": dropped_count,
                "recent_enrollments": recent_enrollments,
                "average_progress": avg_progress,
                "completion_rate": round((completed_count / total_enrollments * 100), 1) if total_enrollments > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching enrollment stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Check Multiple Course Enrollments
# ----------------------------
@router.post("/enrollment/check")
async def check_multiple_enrollments(
    course_ids: List[str],
    auth_result: str = Security(auth.verify)
):
    """Check enrollment status for multiple courses at once"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        enrollments = await prisma.enrollment.find_many(
            where={
                "user_id": user.auth0_id,
                "course_id": {"in": course_ids}
            },
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "short_title": True
                    }
                }
            }
        )
        
        # Create a map of course_id to enrollment status
        enrollment_map = {}
        for enrollment in enrollments:
            enrollment_map[enrollment.course_id] = {
                "enrolled": True,
                "status": enrollment.status,
                "enrollment_id": enrollment.id,
                "enrolled_at": enrollment.enrolled_at,
                "progress_percentage": enrollment.progress_percentage,
                "course_title": enrollment.course.title
            }
        
        # Fill in courses that user is not enrolled in
        for course_id in course_ids:
            if course_id not in enrollment_map:
                enrollment_map[course_id] = {
                    "enrolled": False,
                    "status": None,
                    "enrollment_id": None,
                    "enrolled_at": None,
                    "progress_percentage": 0,
                    "course_title": None
                }
        
        return {
            "status": "success",
            "enrollments": enrollment_map
        }
        
    except Exception as e:
        logger.error(f"Error checking multiple enrollments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )