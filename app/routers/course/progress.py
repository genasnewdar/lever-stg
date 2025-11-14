import time
import logging
from fastapi import APIRouter, HTTPException, Security, status, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, validator
from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/course")
auth = VerifyToken()
start_time = time.time()

# Set up logging
logger = logging.getLogger("course_progress")
logger.setLevel(logging.INFO)

# Pydantic models
class LessonProgressUpdate(BaseModel):
    lesson_id: str
    time_spent: int  # in seconds
    watch_time: int = 0  # for video lessons, in seconds
    is_completed: bool = False
    
    @validator('time_spent')
    def validate_time_spent(cls, v):
        if v < 0:
            raise ValueError('time_spent must be non-negative')
        return v
    
    @validator('watch_time')
    def validate_watch_time(cls, v):
        if v < 0:
            raise ValueError('watch_time must be non-negative')
        return v

class ModuleProgressResponse(BaseModel):
    id: str
    module_id: str
    module_title: str
    is_completed: bool
    completed_at: Optional[datetime] = None
    progress_percentage: float
    time_spent: int
    lessons_progress: List[Dict[str, Any]]

class CourseProgressResponse(BaseModel):
    course_id: str
    course_title: str
    progress_percentage: float
    time_spent: int
    last_accessed_at: datetime
    modules_progress: List[ModuleProgressResponse]

# ----------------------------
# Update Lesson Progress
# ----------------------------
@router.post("/lesson/{lesson_id}/progress")
async def update_lesson_progress(
    lesson_id: str,
    progress_data: LessonProgressUpdate,
    auth_result: str = Security(auth.verify)
):
    """Update progress for a specific lesson"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get lesson with module and course info
        lesson = await prisma.lesson.find_first(
            where={"id": lesson_id, "is_published": True},
            include={
                "module": {
                    "include": {
                        "course": {
                            "select": {
                                "id": True,
                                "title": True,
                                "is_published": True
                            }
                        }
                    }
                }
            }
        )
        
        if not lesson or not lesson.module.course.is_published:
            raise Exception("LESSON_NOT_FOUND")
        
        # Check if user is enrolled
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": lesson.module.course.id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        if not enrollment:
            raise Exception("ENROLLMENT_REQUIRED")
        
        # Get or create course progress
        course_progress = await prisma.courseprogress.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": lesson.module.course.id
            }
        )
        
        if not course_progress:
            course_progress = await prisma.courseprogress.create(
                data={
                    "user_id": user.auth0_id,
                    "course_id": lesson.module.course.id,
                    "progress_percentage": 0,
                    "time_spent": 0,
                    "last_accessed_at": datetime.now(timezone.utc)
                }
            )
        
        # Get or create module progress
        module_progress = await prisma.moduleprogress.find_first(
            where={
                "course_progress_id": course_progress.id,
                "module_id": lesson.module_id
            }
        )
        
        if not module_progress:
            module_progress = await prisma.moduleprogress.create(
                data={
                    "course_progress_id": course_progress.id,
                    "module_id": lesson.module_id,
                    "is_completed": False,
                    "progress_percentage": 0,
                    "time_spent": 0
                }
            )
        
        # Get or create lesson progress
        lesson_progress = await prisma.lessonprogress.find_first(
            where={
                "module_progress_id": module_progress.id,
                "lesson_id": lesson_id
            }
        )
        
        update_data = {
            "time_spent": progress_data.time_spent,
            "watch_time": progress_data.watch_time,
            "is_completed": progress_data.is_completed
        }
        
        if progress_data.is_completed:
            update_data["completed_at"] = datetime.now(timezone.utc)
        
        if lesson_progress:
            # Update existing progress
            lesson_progress = await prisma.lessonprogress.update(
                where={"id": lesson_progress.id},
                data=update_data
            )
        else:
            # Create new progress
            lesson_progress = await prisma.lessonprogress.create(
                data={
                    "module_progress_id": module_progress.id,
                    "lesson_id": lesson_id,
                    **update_data
                }
            )
        
        # Recalculate module progress
        await _recalculate_module_progress(module_progress.id)
        
        # Recalculate course progress
        await _recalculate_course_progress(course_progress.id)
        
        # Update enrollment last accessed time
        await prisma.enrollment.update(
            where={"id": enrollment.id},
            data={"last_accessed_at": datetime.now(timezone.utc)}
        )
        
        return {
            "status": "success",
            "lesson_progress": {
                "id": lesson_progress.id,
                "lesson_id": lesson_progress.lesson_id,
                "is_completed": lesson_progress.is_completed,
                "completed_at": lesson_progress.completed_at,
                "time_spent": lesson_progress.time_spent,
                "watch_time": lesson_progress.watch_time
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating lesson progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Course Progress
# ----------------------------
@router.get("/{course_id}/progress")
async def get_course_progress(
    course_id: str,
    auth_result: str = Security(auth.verify)
):
    """Get detailed progress for a course"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if user is enrolled
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        if not enrollment:
            raise Exception("ENROLLMENT_REQUIRED")
        
        # Get course progress with all related data
        course_progress = await prisma.courseprogress.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id
            },
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "modules": {
                            "where": {"is_published": True},
                            "order": {"order": "asc"},
                            "include": {
                                "lessons": {
                                    "where": {"is_published": True},
                                    "order": {"order": "asc"}
                                }
                            }
                        }
                    }
                },
                "module_progress": {
                    "include": {
                        "module": {
                            "select": {
                                "id": True,
                                "title": True,
                                "order": True
                            }
                        },
                        "lesson_progress": {
                            "include": {
                                "lesson": {
                                    "select": {
                                        "id": True,
                                        "title": True,
                                        "order": True,
                                        "lesson_type": True,
                                        "video_duration": True
                                    }
                                }
                            }
                        }
                    }
                }
            }
        )
        
        if not course_progress:
            # Create initial progress if it doesn't exist
            course_progress = await prisma.courseprogress.create(
                data={
                    "user_id": user.auth0_id,
                    "course_id": course_id,
                    "progress_percentage": 0,
                    "time_spent": 0,
                    "last_accessed_at": datetime.now(timezone.utc)
                },
                include={
                    "course": {
                        "select": {
                            "id": True,
                            "title": True,
                            "modules": {
                                "where": {"is_published": True},
                                "order": {"order": "asc"},
                                "include": {
                                    "lessons": {
                                        "where": {"is_published": True},
                                        "order": {"order": "asc"}
                                    }
                                }
                            }
                        }
                    },
                    "module_progress": True
                }
            )
        
        # Format response
        modules_progress = []
        for module_prog in course_progress.module_progress:
            lessons_progress = []
            for lesson_prog in module_prog.lesson_progress:
                lessons_progress.append({
                    "id": lesson_prog.id,
                    "lesson_id": lesson_prog.lesson_id,
                    "lesson_title": lesson_prog.lesson.title,
                    "lesson_order": lesson_prog.lesson.order,
                    "lesson_type": lesson_prog.lesson.lesson_type,
                    "video_duration": lesson_prog.lesson.video_duration,
                    "is_completed": lesson_prog.is_completed,
                    "completed_at": lesson_prog.completed_at,
                    "time_spent": lesson_prog.time_spent,
                    "watch_time": lesson_prog.watch_time
                })
            
            modules_progress.append({
                "id": module_prog.id,
                "module_id": module_prog.module_id,
                "module_title": module_prog.module.title,
                "module_order": module_prog.module.order,
                "is_completed": module_prog.is_completed,
                "completed_at": module_prog.completed_at,
                "progress_percentage": module_prog.progress_percentage,
                "time_spent": module_prog.time_spent,
                "lessons_progress": sorted(lessons_progress, key=lambda x: x["lesson_order"])
            })
        
        return {
            "status": "success",
            "course_progress": {
                "course_id": course_progress.course_id,
                "course_title": course_progress.course.title,
                "progress_percentage": course_progress.progress_percentage,
                "time_spent": course_progress.time_spent,
                "last_accessed_at": course_progress.last_accessed_at,
                "modules_progress": sorted(modules_progress, key=lambda x: x["module_order"])
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching course progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get User's Overall Progress Statistics
# ----------------------------
@router.get("/progress/stats")
async def get_progress_stats(
    auth_result: str = Security(auth.verify),
    timeframe: str = Query("all", regex="^(week|month|year|all)$")
):
    """Get user's overall progress statistics"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Calculate timeframe
        now = datetime.now(timezone.utc)
        since_date = None
        
        if timeframe == "week":
            since_date = now - timedelta(weeks=1)
        elif timeframe == "month":
            since_date = now - timedelta(days=30)
        elif timeframe == "year":
            since_date = now - timedelta(days=365)
        
        # Build where clause for timeframe
        progress_where = {"user_id": user.auth0_id}
        if since_date:
            progress_where["last_accessed_at"] = {"gte": since_date}
        
        # Get course progress data
        course_progresses = await prisma.courseprogress.find_many(
            where=progress_where,
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "category": True
                    }
                }
            }
        )
        
        # Calculate statistics
        total_courses = len(course_progresses)
        total_time_spent = sum(cp.time_spent for cp in course_progresses)
        avg_progress = sum(cp.progress_percentage for cp in course_progresses) / total_courses if total_courses > 0 else 0
        
        # Count completed courses
        completed_courses = len([cp for cp in course_progresses if cp.progress_percentage == 100])
        
        # Category breakdown
        category_stats = {}
        for cp in course_progresses:
            category = cp.course.category or "Uncategorized"
            if category not in category_stats:
                category_stats[category] = {
                    "count": 0,
                    "total_progress": 0,
                    "time_spent": 0
                }
            category_stats[category]["count"] += 1
            category_stats[category]["total_progress"] += cp.progress_percentage
            category_stats[category]["time_spent"] += cp.time_spent
        
        # Format category stats
        formatted_categories = []
        for category, stats in category_stats.items():
            formatted_categories.append({
                "category": category,
                "course_count": stats["count"],
                "average_progress": round(stats["total_progress"] / stats["count"], 1) if stats["count"] > 0 else 0,
                "time_spent": stats["time_spent"]
            })
        
        # Get recent activity (lessons completed in timeframe)
        recent_lessons = []
        if since_date:
            recent_lesson_progress = await prisma.lessonprogress.find_many(
                where={
                    "completed_at": {"gte": since_date},
                    "is_completed": True,
                    "module_progress": {
                        "course_progress": {
                            "user_id": user.auth0_id
                        }
                    }
                },
                include={
                    "lesson": {
                        "select": {
                            "id": True,
                            "title": True,
                            "module": {
                                "select": {
                                    "title": True,
                                    "course": {
                                        "select": {
                                            "id": True,
                                            "title": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                order={"completed_at": "desc"},
                take=10
            )
            
            recent_lessons = [
                {
                    "lesson_id": lp.lesson_id,
                    "lesson_title": lp.lesson.title,
                    "module_title": lp.lesson.module.title,
                    "course_id": lp.lesson.module.course.id,
                    "course_title": lp.lesson.module.course.title,
                    "completed_at": lp.completed_at,
                    "time_spent": lp.time_spent
                }
                for lp in recent_lesson_progress
            ]
        
        return {
            "status": "success",
            "progress_stats": {
                "timeframe": timeframe,
                "overview": {
                    "total_courses": total_courses,
                    "completed_courses": completed_courses,
                    "average_progress": round(avg_progress, 1),
                    "total_time_spent": total_time_spent,
                    "completion_rate": round((completed_courses / total_courses * 100), 1) if total_courses > 0 else 0
                },
                "categories": sorted(formatted_categories, key=lambda x: x["time_spent"], reverse=True),
                "recent_activity": recent_lessons,
                "time_breakdown": {
                    "total_hours": round(total_time_spent / 3600, 1),
                    "average_per_course": round(total_time_spent / total_courses / 3600, 1) if total_courses > 0 else 0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching progress stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Learning Path Progress
# ----------------------------
@router.get("/progress/learning-path")
async def get_learning_path_progress(
    auth_result: str = Security(auth.verify),
    category: Optional[str] = Query(None)
):
    """Get user's progress across courses in a learning path (category)"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Build where clause
        where_clause = {"user_id": user.auth0_id}
        
        course_progresses = await prisma.courseprogress.find_many(
            where=where_clause,
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "category": True,
                        "subcategory": True,
                        "difficulty_level": True,
                        "estimated_duration": True,
                        "thumbnail_url": True
                    }
                },
                "module_progress": {
                    "select": {
                        "is_completed": True,
                        "module": {
                            "select": {
                                "id": True,
                                "title": True
                            }
                        }
                    }
                }
            },
            order={"last_accessed_at": "desc"}
        )
        
        # Filter by category if specified
        if category:
            course_progresses = [cp for cp in course_progresses if cp.course.category == category]
        
        # Group by category
        learning_paths = {}
        for cp in course_progresses:
            cat = cp.course.category or "Uncategorized"
            if cat not in learning_paths:
                learning_paths[cat] = {
                    "category": cat,
                    "courses": [],
                    "total_progress": 0,
                    "completed_courses": 0,
                    "total_time_spent": 0
                }
            
            # Count completed modules
            completed_modules = sum(1 for mp in cp.module_progress if mp.is_completed)
            total_modules = len(cp.module_progress)
            
            course_data = {
                "course_id": cp.course_id,
                "course_title": cp.course.title,
                "subcategory": cp.course.subcategory,
                "difficulty_level": cp.course.difficulty_level,
                "estimated_duration": cp.course.estimated_duration,
                "thumbnail_url": cp.course.thumbnail_url,
                "progress_percentage": cp.progress_percentage,
                "time_spent": cp.time_spent,
                "last_accessed_at": cp.last_accessed_at,
                "completed_modules": completed_modules,
                "total_modules": total_modules,
                "is_completed": cp.progress_percentage == 100
            }
            
            learning_paths[cat]["courses"].append(course_data)
            learning_paths[cat]["total_progress"] += cp.progress_percentage
            learning_paths[cat]["total_time_spent"] += cp.time_spent
            if cp.progress_percentage == 100:
                learning_paths[cat]["completed_courses"] += 1
        
        # Calculate averages and sort
        formatted_paths = []
        for path_data in learning_paths.values():
            course_count = len(path_data["courses"])
            path_data["average_progress"] = round(path_data["total_progress"] / course_count, 1) if course_count > 0 else 0
            path_data["course_count"] = course_count
            
            # Sort courses within path by progress and last accessed
            path_data["courses"].sort(key=lambda x: (x["progress_percentage"], x["last_accessed_at"]), reverse=True)
            
            formatted_paths.append(path_data)
        
        # Sort paths by total time spent
        formatted_paths.sort(key=lambda x: x["total_time_spent"], reverse=True)
        
        return {
            "status": "success",
            "learning_paths": formatted_paths
        }
        
    except Exception as e:
        logger.error(f"Error fetching learning path progress: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Helper Functions
# ----------------------------
async def _recalculate_module_progress(module_progress_id: str):
    """Recalculate progress percentage for a module based on lesson completion"""
    try:
        # Get all lesson progress for this module
        lesson_progresses = await prisma.lessonprogress.find_many(
            where={"module_progress_id": module_progress_id}
        )
        
        if not lesson_progresses:
            return
        
        # Calculate progress
        total_lessons = len(lesson_progresses)
        completed_lessons = sum(1 for lp in lesson_progresses if lp.is_completed)
        progress_percentage = round((completed_lessons / total_lessons) * 100, 1)
        total_time_spent = sum(lp.time_spent for lp in lesson_progresses)
        
        # Check if module is completed
        is_completed = progress_percentage == 100
        completed_at = datetime.now(timezone.utc) if is_completed else None
        
        # Update module progress
        await prisma.moduleprogress.update(
            where={"id": module_progress_id},
            data={
                "progress_percentage": progress_percentage,
                "time_spent": total_time_spent,
                "is_completed": is_completed,
                "completed_at": completed_at
            }
        )
        
    except Exception as e:
        logger.error(f"Error recalculating module progress: {str(e)}")

async def _recalculate_course_progress(course_progress_id: str):
    """Recalculate progress percentage for a course based on module completion"""
    try:
        # Get all module progress for this course
        module_progresses = await prisma.moduleprogress.find_many(
            where={"course_progress_id": course_progress_id}
        )
        
        if not module_progresses:
            return
        
        # Calculate progress
        total_modules = len(module_progresses)
        total_progress = sum(mp.progress_percentage for mp in module_progresses)
        progress_percentage = round(total_progress / total_modules, 1)
        total_time_spent = sum(mp.time_spent for mp in module_progresses)
        
        # Update course progress and enrollment
        updated_course_progress = await prisma.courseprogress.update(
            where={"id": course_progress_id},
            data={
                "progress_percentage": progress_percentage,
                "time_spent": total_time_spent,
                "last_accessed_at": datetime.now(timezone.utc)
            }
        )
        
        # Update enrollment progress
        await prisma.enrollment.update(
            where={
                "user_id": updated_course_progress.user_id,
                "course_id": updated_course_progress.course_id
            },
            data={"progress_percentage": progress_percentage}
        )
        
    except Exception as e:
        logger.error(f"Error recalculating course progress: {str(e)}")