import time
import logging
from fastapi import APIRouter, HTTPException, Security, status, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/course")
auth = VerifyToken()
start_time = time.time()

# Set up logging
logger = logging.getLogger("course_content")
logger.setLevel(logging.INFO)

# ----------------------------
# Get Course Structure (Modules and Lessons)
# ----------------------------
@router.get("/{course_id}/content")
async def get_course_content(
    course_id: str,
    auth_result: str = Security(auth.verify)
):
    """Get complete course structure with modules and lessons"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if user is enrolled in the course
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        # Get course with modules and lessons
        course = await prisma.course.find_first(
            where={
                "id": course_id,
                "is_published": True
            },
            include={
                "modules": {
                    "where": {"is_published": True},
                    "order": {"order": "asc"},  # Use existing 'order' field
                    "include": {
                        "lessons": {
                            "where": {
                                "OR": [
                                    {"is_preview": True},  # Preview lessons available to all
                                    {"is_published": True} if enrollment else {"is_preview": True}
                                ]
                            },
                            "order": {"order": "asc"},  # Existing 'order' field
                            "include": {
                                "resources": True
                            }
                        }
                    }
                }
            }
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Format course content
        formatted_modules = []
        total_lessons = 0
        total_duration = 0
        
        for module in course.modules:
            lessons = []
            module_duration = 0
            
            for lesson in module.lessons:
                # Check if user can access this lesson
                can_access = enrollment is not None or lesson.is_preview
                
                lesson_data = {
                    "id": lesson.id,
                    "title": lesson.title,
                    "description": lesson.description,
                    "order": lesson.order,
                    "lesson_type": lesson.lesson_type,
                    "video_duration": lesson.video_duration,
                    "is_preview": lesson.is_preview,
                    "can_access": can_access,
                    "resources_count": len(lesson.resources)
                }
                
                # Only include video URL and content if user can access
                if can_access:
                    lesson_data.update({
                        "video_url": lesson.video_url,
                        "content": lesson.content,
                        "resources": [
                            {
                                "id": resource.id,
                                "title": resource.title,
                                "description": resource.description,
                                "file_url": resource.file_url,
                                "file_type": resource.file_type,
                                "file_size": resource.file_size
                            }
                            for resource in lesson.resources
                        ]
                    })
                
                lessons.append(lesson_data)
                total_lessons += 1
                
                if lesson.video_duration:
                    module_duration += lesson.video_duration
            
            formatted_modules.append({
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "order": module.order,
                "estimated_duration": module.estimated_duration,
                "calculated_duration": module_duration,  # Sum of lesson durations
                "lessons_count": len(lessons),
                "lessons": lessons
            })
            
            total_duration += module_duration
        
        return {
            "status": "success",
            "course": {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "overview": course.overview,
                "learning_objectives": course.learning_objectives,
                "prerequisites": course.prerequisites,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "language": course.language,
                "category": course.category,
                "subcategory": course.subcategory
            },
            "content": {
                "modules": formatted_modules,
                "stats": {
                    "total_modules": len(formatted_modules),
                    "total_lessons": total_lessons,
                    "total_duration_seconds": total_duration,
                    "user_enrolled": enrollment is not None
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching course content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Specific Module Content
# ----------------------------
@router.get("/module/{module_id}")
async def get_module_content(
    module_id: str,
    auth_result: str = Security(auth.verify)
):
    """Get detailed content for a specific module"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get module with course info to check enrollment
        module = await prisma.module.find_first(
            where={
                "id": module_id,
                "is_published": True
            },
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "is_published": True
                    }
                },
                "lessons": {
                    "where": {"is_published": True},
                    "order": {"order": "asc"},
                    "include": {
                        "resources": True
                    }
                }
            }
        )
        
        if not module or not module.course.is_published:
            raise Exception("MODULE_NOT_FOUND")
        
        # Check enrollment
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": module.course.id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        # Format lessons with access control
        formatted_lessons = []
        for lesson in module.lessons:
            can_access = enrollment is not None or lesson.is_preview
            
            lesson_data = {
                "id": lesson.id,
                "title": lesson.title,
                "description": lesson.description,
                "order": lesson.order,
                "lesson_type": lesson.lesson_type,
                "video_duration": lesson.video_duration,
                "is_preview": lesson.is_preview,
                "can_access": can_access
            }
            
            if can_access:
                lesson_data.update({
                    "content": lesson.content,
                    "video_url": lesson.video_url,
                    "resources": [
                        {
                            "id": resource.id,
                            "title": resource.title,
                            "description": resource.description,
                            "file_url": resource.file_url,
                            "file_type": resource.file_type,
                            "file_size": resource.file_size
                        }
                        for resource in lesson.resources
                    ]
                })
            
            formatted_lessons.append(lesson_data)
        
        return {
            "status": "success",
            "module": {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "order": module.order,
                "estimated_duration": module.estimated_duration,
                "course": module.course,
                "lessons": formatted_lessons,
                "user_enrolled": enrollment is not None
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching module content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Specific Lesson Content
# ----------------------------
@router.get("/lesson/{lesson_id}")
async def get_lesson_content(
    lesson_id: str,
    auth_result: str = Security(auth.verify)
):
    """Get detailed content for a specific lesson"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get lesson with module and course info
        lesson = await prisma.lesson.find_first(
            where={
                "id": lesson_id,
                "is_published": True
            },
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
                },
                "resources": True
            }
        )
        
        if not lesson or not lesson.module.course.is_published:
            raise Exception("LESSON_NOT_FOUND")
        
        # Check enrollment or if it's a preview lesson
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": lesson.module.course.id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        can_access = enrollment is not None or lesson.is_preview
        
        if not can_access:
            raise Exception("ACCESS_DENIED")
        
        # Update last accessed time if enrolled
        if enrollment:
            await prisma.enrollment.update(
                where={"id": enrollment.id},
                data={"last_accessed_at": datetime.now(timezone.utc)}
            )
        
        # Get previous and next lessons for navigation
        prev_lesson = await prisma.lesson.find_first(
            where={
                "module_id": lesson.module_id,
                "order": {"lt": lesson.order},
                "is_published": True
            },
            order={"order": "desc"}
        )
        
        next_lesson = await prisma.lesson.find_first(
            where={
                "module_id": lesson.module_id,
                "order": {"gt": lesson.order},
                "is_published": True
            },
            order={"order": "asc"}
        )
        
        return {
            "status": "success",
            "lesson": {
                "id": lesson.id,
                "title": lesson.title,
                "description": lesson.description,
                "content": lesson.content,
                "video_url": lesson.video_url,
                "video_duration": lesson.video_duration,
                "order": lesson.order,
                "lesson_type": lesson.lesson_type,
                "is_preview": lesson.is_preview,
                "module": {
                    "id": lesson.module.id,
                    "title": lesson.module.title,
                    "course": lesson.module.course
                },
                "resources": [
                    {
                        "id": resource.id,
                        "title": resource.title,
                        "description": resource.description,
                        "file_url": resource.file_url,
                        "file_type": resource.file_type,
                        "file_size": resource.file_size
                    }
                    for resource in lesson.resources
                ],
                "navigation": {
                    "previous_lesson": {
                        "id": prev_lesson.id,
                        "title": prev_lesson.title
                    } if prev_lesson else None,
                    "next_lesson": {
                        "id": next_lesson.id,
                        "title": next_lesson.title
                    } if next_lesson else None
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching lesson content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Course Announcements
# ----------------------------
@router.get("/{course_id}/announcements")
async def get_course_announcements(
    course_id: str,
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50)
):
    """Get announcements for a course"""
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
        
        skip = (page - 1) * per_page
        
        total_count = await prisma.announcement.count(
            where={"course_id": course_id}
        )
        
        announcements = await prisma.announcement.find_many(
            where={"course_id": course_id},
            skip=skip,
            take=per_page,
            order={"created_at": "desc"}
        )
        
        return {
            "status": "success",
            "announcements": announcements,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching course announcements: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Course Assignments
# ----------------------------
@router.get("/{course_id}/assignments")
async def get_course_assignments(
    course_id: str,
    auth_result: str = Security(auth.verify),
    status_filter: Optional[str] = Query(None)
):
    """Get assignments for a course"""
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
        
        # Get assignments with user's submissions
        assignments = await prisma.assignment.find_many(
            where={
                "course_id": course_id,
                "is_published": True
            },
            order={"due_date": "asc"},
            include={
                "submissions": {
                    "where": {"user_id": user.auth0_id}
                }
            }
        )
        
        formatted_assignments = []
        for assignment in assignments:
            user_submission = assignment.submissions[0] if assignment.submissions else None
            
            assignment_data = {
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "instructions": assignment.instructions,
                "due_date": assignment.due_date,
                "points": assignment.points,
                "created_at": assignment.created_at,
                "submission": {
                    "id": user_submission.id,
                    "submitted_at": user_submission.submitted_at,
                    "status": user_submission.status,
                    "grade": user_submission.grade,
                    "feedback": user_submission.feedback,
                    "graded_at": user_submission.graded_at
                } if user_submission else None,
                "is_overdue": assignment.due_date and assignment.due_date < datetime.now(timezone.utc) and not user_submission,
                "can_submit": not user_submission or user_submission.status == "RETURNED"
            }
            
            # Apply status filter if provided
            if status_filter:
                if status_filter == "submitted" and not user_submission:
                    continue
                elif status_filter == "not_submitted" and user_submission:
                    continue
                elif status_filter == "graded" and (not user_submission or user_submission.status != "GRADED"):
                    continue
                elif status_filter == "overdue" and not assignment_data["is_overdue"]:
                    continue
            
            formatted_assignments.append(assignment_data)
        
        return {
            "status": "success",
            "assignments": formatted_assignments
        }
        
    except Exception as e:
        logger.error(f"Error fetching course assignments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Course Forums
# ----------------------------
@router.get("/{course_id}/forums")
async def get_course_forums(
    course_id: str,
    auth_result: str = Security(auth.verify)
):
    """Get discussion forums for a course"""
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
        
        forums = await prisma.forum.find_many(
            where={
                "course_id": course_id,
                "is_active": True
            },
            include={
                "_count": {
                    "select": {"posts": True}
                }
            }
        )
        
        formatted_forums = []
        for forum in forums:
            # Get latest post for each forum
            latest_post = await prisma.forumpost.find_first(
                where={"forum_id": forum.id},
                order={"created_at": "desc"},
                include={
                    "author": {
                        "select": {
                            "auth0_id": True,
                            "full_name": True,
                            "picture": True
                        }
                    }
                }
            )
            
            formatted_forums.append({
                "id": forum.id,
                "title": forum.title,
                "description": forum.description,
                "created_at": forum.created_at,
                "posts_count": forum._count.posts if hasattr(forum, '_count') else 0,
                "latest_post": {
                    "id": latest_post.id,
                    "title": latest_post.title,
                    "created_at": latest_post.created_at,
                    "author": latest_post.author
                } if latest_post else None
            })
        
        return {
            "status": "success",
            "forums": formatted_forums
        }
        
    except Exception as e:
        logger.error(f"Error fetching course forums: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Search Course Content
# ----------------------------
@router.get("/{course_id}/search")
async def search_course_content(
    course_id: str,
    q: str = Query(..., min_length=2),
    auth_result: str = Security(auth.verify),
    content_type: Optional[str] = Query(None)
):
    """Search within course content (lessons, resources, announcements)"""
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
        
        search_term = q.strip()
        results = {"lessons": [], "resources": [], "announcements": []}
        
        # Search lessons (only if not filtering or filtering for lessons)
        if not content_type or content_type == "lessons":
            lessons = await prisma.lesson.find_many(
                where={
                    "module": {"course_id": course_id},
                    "is_published": True,
                    "OR": [
                        {"title": {"contains": search_term, "mode": "insensitive"}},
                        {"description": {"contains": search_term, "mode": "insensitive"}},
                        {"content": {"contains": search_term, "mode": "insensitive"}}
                    ]
                },
                include={
                    "module": {
                        "select": {
                            "id": True,
                            "title": True
                        }
                    }
                }
            )
            
            results["lessons"] = [
                {
                    "id": lesson.id,
                    "title": lesson.title,
                    "description": lesson.description,
                    "lesson_type": lesson.lesson_type,
                    "module": lesson.module,
                    "match_type": "lesson"
                }
                for lesson in lessons
            ]
        
        # Search resources (only if not filtering or filtering for resources)
        if not content_type or content_type == "resources":
            resources = await prisma.lessonresource.find_many(
                where={
                    "lesson": {
                        "module": {"course_id": course_id},
                        "is_published": True
                    },
                    "OR": [
                        {"title": {"contains": search_term, "mode": "insensitive"}},
                        {"description": {"contains": search_term, "mode": "insensitive"}}
                    ]
                },
                include={
                    "lesson": {
                        "select": {
                            "id": True,
                            "title": True,
                            "module": {
                                "select": {
                                    "id": True,
                                    "title": True
                                }
                            }
                        }
                    }
                }
            )
            
            results["resources"] = [
                {
                    "id": resource.id,
                    "title": resource.title,
                    "description": resource.description,
                    "file_type": resource.file_type,
                    "lesson": resource.lesson,
                    "match_type": "resource"
                }
                for resource in resources
            ]
        
        # Search announcements (only if not filtering or filtering for announcements)
        if not content_type or content_type == "announcements":
            announcements = await prisma.announcement.find_many(
                where={
                    "course_id": course_id,
                    "OR": [
                        {"title": {"contains": search_term, "mode": "insensitive"}},
                        {"content": {"contains": search_term, "mode": "insensitive"}}
                    ]
                }
            )
            
            results["announcements"] = [
                {
                    "id": announcement.id,
                    "title": announcement.title,
                    "content": announcement.content[:200] + "..." if len(announcement.content) > 200 else announcement.content,
                    "created_at": announcement.created_at,
                    "is_important": announcement.is_important,
                    "match_type": "announcement"
                }
                for announcement in announcements
            ]
        
        total_results = len(results["lessons"]) + len(results["resources"]) + len(results["announcements"])
        
        return {
            "status": "success",
            "search_query": search_term,
            "results": results,
            "total_results": total_results
        }
        
    except Exception as e:
        logger.error(f"Error searching course content: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )