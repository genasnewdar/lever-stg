import time
import json
import logging
from fastapi import APIRouter, HTTPException, Security, status, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/admin/course")
auth = VerifyToken()
start_time = time.time()

# Set up logging
logger = logging.getLogger("admin_course")
logger.setLevel(logging.INFO)

# ----------------------------
# Pydantic Models for Payload
# ----------------------------
class LessonResourceCreate(BaseModel):
    title: str
    description: Optional[str] = None
    file_url: str
    file_type: str
    file_size: Optional[int] = None

class LessonCreate(BaseModel):
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    video_url: Optional[str] = None
    video_duration: Optional[int] = None
    order: int
    lesson_type: str = "VIDEO"  # VIDEO, TEXT, QUIZ, ASSIGNMENT, READING, INTERACTIVE
    is_published: Optional[bool] = True
    is_preview: Optional[bool] = False
    resources: Optional[List[LessonResourceCreate]] = []

class ModuleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order: int
    is_published: Optional[bool] = True
    estimated_duration: Optional[int] = None
    lessons: List[LessonCreate] = []

class AdminCreateCourseRequest(BaseModel):
    title: str
    short_title: Optional[str] = None
    description: Optional[str] = None
    overview: Optional[str] = None
    learning_objectives: Optional[str] = None
    prerequisites: Optional[str] = None
    difficulty_level: str = "BEGINNER"  # BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
    estimated_duration: Optional[int] = None
    language: str = "en"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_preview_url: Optional[str] = None
    price: Optional[float] = None
    is_free: Optional[bool] = True
    is_published: Optional[bool] = False
    is_featured: Optional[bool] = False
    modules: List[ModuleCreate] = []

class CourseUpdateRequest(BaseModel):
    title: Optional[str] = None
    short_title: Optional[str] = None
    description: Optional[str] = None
    overview: Optional[str] = None
    learning_objectives: Optional[str] = None
    prerequisites: Optional[str] = None
    difficulty_level: Optional[str] = None
    estimated_duration: Optional[int] = None
    language: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_preview_url: Optional[str] = None
    price: Optional[float] = None
    is_free: Optional[bool] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None

# ------------------------------------------
# Helper functions
# ------------------------------------------
def wrap_create_field(data: dict, field: str):
    """
    If the given field exists in data and is a list,
    wrap it in a dict with a "create" key for Prisma nested writes.
    """
    if field in data and isinstance(data[field], list):
        data[field] = {"create": data[field]}

def process_lesson(lesson: dict):
    """Process a single lesson dictionary to wrap resources with "create"."""
    wrap_create_field(lesson, "resources")
    return lesson

def process_module(module: dict):
    """Process a single module dictionary to wrap lessons with "create"."""
    wrap_create_field(module, "lessons")
    if "lessons" in module and "create" in module["lessons"]:
        for idx, lesson in enumerate(module["lessons"]["create"]):
            module["lessons"]["create"][idx] = process_lesson(lesson)
    return module

# ----------------------------
# Admin Create Course Endpoint
# ----------------------------
@router.post("")
async def create_course(payload: AdminCreateCourseRequest, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Convert payload to dict and add creator/instructor info
        course_data = payload.model_dump(exclude_none=True)
        course_data["creator_id"] = user.auth0_id
        course_data["instructor_id"] = user.auth0_id  # Default to creator, can be changed later
        
        # Process nested relationships
        if "modules" in course_data:
            modules_list = course_data["modules"]
            for module in modules_list:
                module = process_module(module)
            course_data["modules"] = {"create": modules_list}

        created_course = await prisma.course.create(data=course_data)
        return created_course
        
    except Exception as e:
        logger.error("Error creating course: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Update Course Endpoint
# ----------------------------
@router.put("/{id}")
async def update_course(id: str, payload: CourseUpdateRequest, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and user has permission
        course = await prisma.course.find_first(
            where={"id": id}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Only creator or instructor can update
        if course.creator_id != user.auth0_id and course.instructor_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_UPDATE_COURSE")
        
        update_data = payload.model_dump(exclude_none=True)
        if not update_data:
            raise Exception("NO_UPDATE_DATA_PROVIDED")
        
        updated_course = await prisma.course.update(
            where={"id": id},
            data=update_data
        )
        return updated_course
        
    except Exception as e:
        logger.error("Error updating course: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Get Course Details
# ----------------------------
@router.get("/{id}")
async def get_course(id: str, auth_result: str = Security(auth.verify)):
    try:
        course = await prisma.course.find_first(
            where={"id": id},
            include={
                "modules": {
                    "include": {
                        "lessons": {
                            "include": {
                                "resources": True
                            }
                        }
                    }
                },
                "instructor": True,
                "creator": True
            }
        )
        
        if not course:
            raise HTTPException(status_code=404, detail="COURSE_NOT_FOUND")
        
        return course
        
    except Exception as e:
        logger.error("Error fetching course: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin List Courses
# ----------------------------
@router.get("")
async def list_courses(
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    category: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    is_published: Optional[bool] = Query(None)
):
    try:
        skip = (page - 1) * per_page
        
        # Build where clause
        where_clause = {}
        if category:
            where_clause["category"] = category
        if subject:
            where_clause["subject"] = subject
        if is_published is not None:
            where_clause["is_published"] = is_published

        total_count = await prisma.course.count(where=where_clause)
        
        courses = await prisma.course.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order={"created_at": "desc"},
            include={"instructor": True}
        )
        
        result = []
        for c in courses:
            result.append({
                "id": c.id,
                "title": c.title,
                "short_title": c.short_title,
                "description": c.description,
                "difficulty_level": c.difficulty_level,
                "language": c.language,
                "category": c.category,
                "subcategory": c.subcategory,
                "thumbnail_url": c.thumbnail_url,
                "price": c.price,
                "is_free": c.is_free,
                "is_published": c.is_published,
                "is_featured": c.is_featured,
                "rating": c.rating,
                "rating_count": c.rating_count,
                "enrollment_count": c.enrollment_count,
                "created_at": c.created_at,
                "instructor": {
                    "id": c.instructor.auth0_id,
                    "full_name": c.instructor.full_name,
                    "email": c.instructor.email
                } if c.instructor else None,
                "stats": {
                    "enrollments": c._count.enrollments if hasattr(c, '_count') else 0,
                    "modules": c._count.modules if hasattr(c, '_count') else 0
                }
            })
        
        return {
            "status": "success",
            "courses": courses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error("Error listing courses: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Delete Course
# ----------------------------
@router.delete("/{id}")
async def delete_course(id: str, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and user has permission
        course = await prisma.course.find_first(
            where={"id": id}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Only creator can delete
        if course.creator_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_DELETE_COURSE")
        
        # Check if course has enrollments
        enrollment_count = await prisma.enrollment.count(
            where={"course_id": id}
        )
        if enrollment_count > 0:
            raise Exception("CANNOT_DELETE_COURSE_WITH_ENROLLMENTS")
        
        await prisma.course.delete(where={"id": id})
        
        return {"status": "success", "message": "Course deleted successfully"}
        
    except Exception as e:
        logger.error("Error deleting course: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Publish/Unpublish Course
# ----------------------------
@router.patch("/{id}/publish")
async def toggle_course_publication(
    id: str, 
    publish: bool = Query(..., description="Whether to publish or unpublish the course"),
    auth_result: str = Security(auth.verify)
):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and user has permission
        course = await prisma.course.find_first(
            where={"id": id}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        updated_course = await prisma.course.update(
            where={"id": id},
            data={"is_published": publish}
        )
        
        action = "published" if publish else "unpublished"
        return {
            "status": "success", 
            "message": f"Course {action} successfully",
            "course": updated_course
        }
        
    except Exception as e:
        logger.error("Error toggling course publication: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Get Course Analytics
# ----------------------------
@router.get("/{id}/analytics")
async def get_course_analytics(id: str, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and user has permission
        course = await prisma.course.find_first(
            where={"id": id}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Only creator or instructor can view analytics
        if course.creator_id != user.auth0_id and course.instructor_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_VIEW_ANALYTICS")
        
        # Get enrollment statistics
        total_enrollments = await prisma.enrollment.count(
            where={"course_id": id}
        )
        
        active_enrollments = await prisma.enrollment.count(
            where={"course_id": id, "status": "ACTIVE"}
        )
        
        completed_enrollments = await prisma.enrollment.count(
            where={"course_id": id, "status": "COMPLETED"}
        )
        
        # Get average progress
        progress_records = await prisma.courseprogress.find_many(
            where={"course_id": id}
        )
        
        avg_progress = 0
        if progress_records:
            total_progress = sum(p.progress_percentage for p in progress_records)
            avg_progress = total_progress / len(progress_records)
        
        # Get recent enrollments (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
        recent_enrollments = await prisma.enrollment.count(
            where={
                "course_id": id,
                "enrolled_at": {"gte": thirty_days_ago}
            }
        )
        
        # Get module completion rates
        modules = await prisma.module.find_many(
            where={"course_id": id},
            include={
                "_count": {
                    "select": {"module_progress": True}
                }
            }
        )
        
        module_stats = []
        for module in modules:
            completed_count = await prisma.moduleprogress.count(
                where={
                    "module_id": module.id,
                    "is_completed": True
                }
            )
            
            module_stats.append({
                "module_id": module.id,
                "module_title": module.title,
                "total_attempts": module._count.module_progress if hasattr(module, '_count') else 0,
                "completed_count": completed_count,
                "completion_rate": (completed_count / module._count.module_progress * 100) if hasattr(module, '_count') and module._count.module_progress > 0 else 0
            })
        
        return {
            "status": "success",
            "analytics": {
                "enrollments": {
                    "total": total_enrollments,
                    "active": active_enrollments,
                    "completed": completed_enrollments,
                    "recent_30_days": recent_enrollments
                },
                "progress": {
                    "average_progress_percentage": round(avg_progress, 2)
                },
                "modules": module_stats,
                "course_info": {
                    "title": course.title,
                    "rating": course.rating,
                    "rating_count": course.rating_count
                }
            }
        }
        
    except Exception as e:
        logger.error("Error fetching course analytics: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Get Course Enrollments
# ----------------------------
@router.get("/{id}/enrollments")
async def get_course_enrollments(
    id: str,
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    status_filter: Optional[str] = Query(None)
):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and user has permission
        course = await prisma.course.find_first(
            where={"id": id}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Only creator or instructor can view enrollments
        if course.creator_id != user.auth0_id and course.instructor_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_VIEW_ENROLLMENTS")
        
        skip = (page - 1) * per_page
        
        where_clause = {"course_id": id}
        if status_filter:
            where_clause["status"] = status_filter
        
        total_count = await prisma.enrollment.count(where=where_clause)
        
        enrollments = await prisma.enrollment.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order={"enrolled_at": "desc"},
            include={
                "user": True,
                "course": True
            }
        )
        
        enrollment_data = []
        for enrollment in enrollments:
            # Get course progress for this user
            progress = await prisma.courseprogress.find_first(
                where={
                    "user_id": enrollment.user_id,
                    "course_id": id
                }
            )
            
            enrollment_data.append({
                "id": enrollment.id,
                "status": enrollment.status,
                "enrolled_at": enrollment.enrolled_at,
                "completed_at": enrollment.completed_at,
                "last_accessed_at": enrollment.last_accessed_at,
                "progress_percentage": enrollment.progress_percentage,
                "user": {
                    "id": enrollment.user.auth0_id,
                    "full_name": enrollment.user.full_name,
                    "email": enrollment.user.email,
                    "picture": enrollment.user.picture
                },
                "detailed_progress": {
                    "progress_percentage": progress.progress_percentage if progress else 0,
                    "time_spent": progress.time_spent if progress else 0,
                    "last_accessed_at": progress.last_accessed_at if progress else None
                } if progress else None
            })
        
        return {
            "status": "success",
            "enrollments": enrollment_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error("Error fetching course enrollments: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Add Module to Course
# ----------------------------
@router.post("/{id}/modules")
async def add_module_to_course(id: str, payload: ModuleCreate, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and user has permission
        course = await prisma.course.find_first(
            where={"id": id}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Only creator or instructor can add modules
        if course.creator_id != user.auth0_id and course.instructor_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_MODIFY_COURSE")
        
        module_data = payload.model_dump(exclude_none=True)
        module_data["course_id"] = id
        
        # Process lessons
        if "lessons" in module_data:
            lessons_list = module_data["lessons"]
            for lesson in lessons_list:
                lesson = process_lesson(lesson)
            module_data["lessons"] = {"create": lessons_list}
        
        created_module = await prisma.module.create(data=module_data)
        return created_module
        
    except Exception as e:
        logger.error("Error adding module to course: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Update Module
# ----------------------------
@router.put("/modules/{module_id}")
async def update_module(module_id: str, payload: dict, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get module and check permissions
        module = await prisma.module.find_first(
            where={"id": module_id},
            include={"course": True}
        )
        if not module:
            raise Exception("MODULE_NOT_FOUND")
        
        # Only creator or instructor can update modules
        if module.course.creator_id != user.auth0_id and module.course.instructor_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_MODIFY_MODULE")
        
        # Remove None values
        update_data = {k: v for k, v in payload.items() if v is not None}
        if not update_data:
            raise Exception("NO_UPDATE_DATA_PROVIDED")
        
        updated_module = await prisma.module.update(
            where={"id": module_id},
            data=update_data
        )
        return updated_module
        
    except Exception as e:
        logger.error("Error updating module: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Admin Delete Module
# ----------------------------
@router.delete("/modules/{module_id}")
async def delete_module(module_id: str, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get module and check permissions
        module = await prisma.module.find_first(
            where={"id": module_id},
            include={"course": True}
        )
        if not module:
            raise Exception("MODULE_NOT_FOUND")
        
        # Only creator or instructor can delete modules
        if module.course.creator_id != user.auth0_id and module.course.instructor_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_TO_DELETE_MODULE")
        
        await prisma.module.delete(where={"id": module_id})
        
        return {"status": "success", "message": "Module deleted successfully"}
        
    except Exception as e:
        logger.error("Error deleting module: %s", e)
        raise HTTPException(status_code=400, detail=str(e))