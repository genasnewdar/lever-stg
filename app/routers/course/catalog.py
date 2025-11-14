import time
import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from app.singleton import prisma

router = APIRouter(prefix="/api/course")
start_time = time.time()

# Set up logging
logger = logging.getLogger("course_catalog")
logger.setLevel(logging.INFO)

# ----------------------------
# Public Course Catalog
# ----------------------------
@router.get("/public")
async def list_public_courses(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    category: Optional[str] = Query(None),
    subcategory: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    is_free: Optional[bool] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    search: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|rating|enrollment_count|title|price)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    List all published courses with filtering and search capabilities.
    No authentication required for public course browsing.
    """
    try:
        skip = (page - 1) * per_page
        
        # Build where clause for published courses only
        where_clause = {"is_published": True}
        
        if category:
            where_clause["category"] = category
        if subcategory:
            where_clause["subcategory"] = subcategory
        if difficulty:
            where_clause["difficulty_level"] = difficulty
        if language:
            where_clause["language"] = language
        if is_free is not None:
            where_clause["is_free"] = is_free
        if min_rating is not None:
            where_clause["rating"] = {"gte": min_rating}
        
        # Handle search across multiple fields
        if search:
            search_term = search.strip()
            where_clause["OR"] = [
                {"title": {"contains": search_term, "mode": "insensitive"}},
                {"description": {"contains": search_term, "mode": "insensitive"}},
                {"overview": {"contains": search_term, "mode": "insensitive"}},
                {"category": {"contains": search_term, "mode": "insensitive"}},
                {"subcategory": {"contains": search_term, "mode": "insensitive"}}
            ]
        
        # Get total count
        total_count = await prisma.course.count(where=where_clause)
        
        # Simple query following your admin pattern - no _count
        courses = await prisma.course.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order={sort_by: sort_order},
            include={
                "instructor": True
            }
        )
        
        # Simple formatting - use fields already available on the model
        formatted_courses = [
            {
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "overview": course.overview,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "language": course.language,
                "category": course.category,
                "subcategory": course.subcategory,
                "thumbnail_url": course.thumbnail_url,
                "video_preview_url": course.video_preview_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "created_at": course.created_at,
                "instructor": (
                    {
                        "auth0_id": course.instructor.auth0_id,
                        "full_name": course.instructor.full_name,
                        "picture": course.instructor.picture,
                        "bio": getattr(course.instructor, "bio", None)
                    } if course.instructor else None
                )
            }
            for course in courses
        ]
        
        return {
            "status": "success",
            "courses": formatted_courses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error("Error listing public courses: %s", str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve courses")
# ----------------------------
# Get Available Categories
# ----------------------------
@router.get("/categories")
async def get_course_categories():
    """
    Get all available course categories and subcategories.
    Returns unique categories from published courses.
    """
    try:
        # Get distinct categories and subcategories
        categories_result = await prisma.course.find_many(
            where={"is_published": True},
            select={
                "category": True,
                "subcategory": True
            },
            distinct=["category", "subcategory"]
        )
        
        # Organize categories and subcategories
        category_map = {}
        for item in categories_result:
            if item.category:
                if item.category not in category_map:
                    category_map[item.category] = set()
                if item.subcategory:
                    category_map[item.category].add(item.subcategory)
        
        # Convert to list format
        categories = []
        for category, subcategories in category_map.items():
            categories.append({
                "name": category,
                "subcategories": sorted(list(subcategories))
            })
        
        # Get category counts
        category_counts = {}
        for category in category_map.keys():
            count = await prisma.course.count(
                where={
                    "is_published": True,
                    "category": category
                }
            )
            category_counts[category] = count
        
        return {
            "status": "success",
            "categories": sorted(categories, key=lambda x: x["name"]),
            "category_counts": category_counts
        }
        
    except Exception as e:
        logger.error("Error fetching course categories: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Get Featured Courses
# ----------------------------
@router.get("/featured")
async def get_featured_courses(
    limit: int = Query(8, ge=1, le=20)
):
    """
    Get featured courses for homepage or promotional sections.
    """
    try:
        featured_courses = await prisma.course.find_many(
            where={
                "is_published": True,
                "is_featured": True
            },
            take=limit,
            order={"rating": "desc"},
            include={
                "instructor": True
            }
        )
        
        formatted_courses = []
        for course in featured_courses:
            # Compute modules count without using _count include
            modules_count = await prisma.module.count(where={"course_id": course.id})
            formatted_courses.append({
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "category": course.category,
                "thumbnail_url": course.thumbnail_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "instructor": (
                    {
                        "auth0_id": course.instructor.auth0_id,
                        "full_name": course.instructor.full_name,
                        "picture": course.instructor.picture
                    } if course.instructor else None
                ),
                "stats": {
                    "modules_count": modules_count,
                    "enrollments_count": course.enrollment_count
                }
            })
        
        return {
            "status": "success",
            "featured_courses": formatted_courses
        }
        
    except Exception as e:
        logger.error("Error fetching featured courses: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Advanced Course Search
# ----------------------------
@router.get("/search")
async def search_courses(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    filters: Optional[str] = Query(None)  # JSON string of additional filters
):
    """
    Advanced course search with multiple criteria.
    """
    try:
        import json
        
        skip = (page - 1) * per_page
        search_term = q.strip()
        
        # Base where clause
        where_clause = {
            "is_published": True,
            "OR": [
                {"title": {"contains": search_term, "mode": "insensitive"}},
                {"description": {"contains": search_term, "mode": "insensitive"}},
                {"overview": {"contains": search_term, "mode": "insensitive"}},
                {"learning_objectives": {"contains": search_term, "mode": "insensitive"}},
                {"category": {"contains": search_term, "mode": "insensitive"}},
                {"subcategory": {"contains": search_term, "mode": "insensitive"}},
                {
                    "instructor": {
                        "full_name": {"contains": search_term, "mode": "insensitive"}
                    }
                }
            ]
        }
        
        # Apply additional filters if provided
        if filters:
            try:
                additional_filters = json.loads(filters)
                where_clause["AND"] = []
                
                if additional_filters.get("category"):
                    where_clause["AND"].append({"category": additional_filters["category"]})
                if additional_filters.get("difficulty"):
                    where_clause["AND"].append({"difficulty_level": additional_filters["difficulty"]})
                if additional_filters.get("is_free") is not None:
                    where_clause["AND"].append({"is_free": additional_filters["is_free"]})
                if additional_filters.get("min_rating"):
                    where_clause["AND"].append({"rating": {"gte": additional_filters["min_rating"]}})
                if additional_filters.get("max_price"):
                    where_clause["AND"].append({
                        "OR": [
                            {"is_free": True},
                            {"price": {"lte": additional_filters["max_price"]}}
                        ]
                    })
                
            except json.JSONDecodeError:
                logger.warning("Invalid filters JSON provided: %s", filters)
        
        total_count = await prisma.course.count(where=where_clause)
        
        courses = await prisma.course.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order={"rating": "desc"},  # Prioritize highly rated courses in search
            include={
                "instructor": True
            }
        )
        
        formatted_courses = []
        for course in courses:
            modules_count = await prisma.module.count(where={"course_id": course.id})
            formatted_courses.append({
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "category": course.category,
                "subcategory": course.subcategory,
                "thumbnail_url": course.thumbnail_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "instructor": (
                    {
                        "auth0_id": course.instructor.auth0_id,
                        "full_name": course.instructor.full_name,
                        "picture": course.instructor.picture
                    } if course.instructor else None
                ),
                "stats": {
                    "modules_count": modules_count,
                    "enrollments_count": course.enrollment_count
                }
            })
        
        return {
            "status": "success",
            "search_query": search_term,
            "courses": formatted_courses,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error("Error searching courses: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Get Course Categories with Stats
# ----------------------------
@router.get("/categories")
async def get_course_categories():
    """
    Get all available course categories and subcategories with course counts.
    Returns organized category structure for filtering UI.
    """
    try:
        # Get all published courses with categories
        courses = await prisma.course.find_many(
            where={"is_published": True},
            select={
                "category": True,
                "subcategory": True,
                "difficulty_level": True,
                "is_free": True,
                "language": True
            }
        )
        
        # Organize data
        category_map = {}
        difficulty_counts = {}
        language_counts = {}
        price_counts = {"free": 0, "paid": 0}
        
        for course in courses:
            # Categories and subcategories
            if course.category:
                if course.category not in category_map:
                    category_map[course.category] = {
                        "count": 0,
                        "subcategories": {}
                    }
                category_map[course.category]["count"] += 1
                
                if course.subcategory:
                    subcat = course.subcategory
                    if subcat not in category_map[course.category]["subcategories"]:
                        category_map[course.category]["subcategories"][subcat] = 0
                    category_map[course.category]["subcategories"][subcat] += 1
            
            # Difficulty levels
            if course.difficulty_level:
                difficulty_counts[course.difficulty_level] = difficulty_counts.get(course.difficulty_level, 0) + 1
            
            # Languages
            if course.language:
                language_counts[course.language] = language_counts.get(course.language, 0) + 1
            
            # Price categories
            if course.is_free:
                price_counts["free"] += 1
            else:
                price_counts["paid"] += 1
        
        # Format categories
        categories = []
        for cat_name, cat_data in category_map.items():
            subcategories = [
                {"name": subcat, "count": count}
                for subcat, count in cat_data["subcategories"].items()
            ]
            categories.append({
                "name": cat_name,
                "count": cat_data["count"],
                "subcategories": sorted(subcategories, key=lambda x: x["name"])
            })
        
        return {
            "status": "success",
            "categories": sorted(categories, key=lambda x: x["name"]),
            "filters": {
                "difficulty_levels": [
                    {"name": diff, "count": count}
                    for diff, count in sorted(difficulty_counts.items())
                ],
                "languages": [
                    {"name": lang, "count": count}
                    for lang, count in sorted(language_counts.items())
                ],
                "price_options": [
                    {"name": "Free", "value": "free", "count": price_counts["free"]},
                    {"name": "Paid", "value": "paid", "count": price_counts["paid"]}
                ]
            },
            "total_published_courses": len(courses)
        }
        
    except Exception as e:
        logger.error("Error fetching course categories: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Get Featured Courses
# ----------------------------
@router.get("/featured")
async def get_featured_courses(
    limit: int = Query(8, ge=1, le=20)
):
    """
    Get featured courses for homepage or promotional sections.
    Combines explicitly featured courses with highly-rated popular courses.
    """
    try:
        # Get explicitly featured courses
        featured_courses = await prisma.course.find_many(
            where={
                "is_published": True,
                "is_featured": True
            },
            order={"rating": "desc"},
            include={
                "instructor": True
            }
        )
        
        # If we don't have enough featured courses, supplement with popular ones
        needed_count = limit - len(featured_courses)
        popular_courses = []
        
        if needed_count > 0:
            featured_ids = [course.id for course in featured_courses]
            where_clause = {
                "is_published": True,
                "rating": {"gte": 4.0},  # Only highly rated courses
                "enrollment_count": {"gte": 10}  # Only courses with decent enrollment
            }
            
            if featured_ids:
                where_clause["id"] = {"notIn": featured_ids}
            
            popular_courses = await prisma.course.find_many(
                where=where_clause,
                take=needed_count,
                order=[
                    {"rating": "desc"},
                    {"enrollment_count": "desc"}
                ],
                include={
                    "instructor": True
                }
            )
        
        # Combine and format courses
        all_courses = featured_courses + popular_courses
        formatted_courses = []
        
        for course in all_courses[:limit]:
            modules_count = await prisma.module.count(where={"course_id": course.id})
            formatted_courses.append({
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "category": course.category,
                "subcategory": course.subcategory,
                "thumbnail_url": course.thumbnail_url,
                "video_preview_url": course.video_preview_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "is_featured": course.is_featured,
                "instructor": (
                    {
                        "auth0_id": course.instructor.auth0_id,
                        "full_name": course.instructor.full_name,
                        "picture": course.instructor.picture
                    } if course.instructor else None
                ),
                "stats": {
                    "modules_count": modules_count,
                    "enrollments_count": course.enrollment_count
                }
            })
        
        return {
            "status": "success",
            "featured_courses": formatted_courses,
            "metadata": {
                "explicitly_featured": len(featured_courses),
                "popular_supplements": len(popular_courses),
                "total_returned": len(formatted_courses)
            }
        }
        
    except Exception as e:
        logger.error("Error fetching featured courses: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Get Similar Courses
# ----------------------------
@router.get("/{course_id}/similar")
async def get_similar_courses(
    course_id: str,
    limit: int = Query(6, ge=1, le=20)
):
    """
    Get courses similar to the specified course based on category, difficulty, and instructor.
    """
    try:
        # Get the base course
        base_course = await prisma.course.find_first(
            where={"id": course_id, "is_published": True},
            select={
                "category": True,
                "subcategory": True,
                "difficulty_level": True,
                "instructor_id": True
            }
        )
        
        if not base_course:
            raise HTTPException(status_code=404, detail="COURSE_NOT_FOUND")
        
        # Build similarity query - prioritize same category, then subcategory, then instructor
        similar_courses = await prisma.course.find_many(
            where={
                "is_published": True,
                "id": {"not": course_id},  # Exclude the base course itself
                "OR": [
                    # Same category and subcategory (highest priority)
                    {
                        "category": base_course.category,
                        "subcategory": base_course.subcategory
                    },
                    # Same category, different subcategory
                    {
                        "category": base_course.category,
                        "subcategory": {"not": base_course.subcategory}
                    },
                    # Same instructor
                    {
                        "instructor_id": base_course.instructor_id
                    }
                ]
            },
            take=limit * 2,  # Get more than needed to allow for sorting
            include={
                "instructor": True
            }
        )
        
        # Score and sort by similarity
        scored_courses = []
        for course in similar_courses:
            score = 0
            
            # Category match
            if course.category == base_course.category:
                score += 3
                # Subcategory match
                if course.subcategory == base_course.subcategory:
                    score += 2
            
            # Same instructor
            if course.instructor_id == base_course.instructor_id:
                score += 2
            
            # Same difficulty level
            if course.difficulty_level == base_course.difficulty_level:
                score += 1
            
            # Boost for popular courses
            if course.rating and course.rating >= 4.0:
                score += 1
            if course.enrollment_count >= 50:
                score += 1
            
            scored_courses.append((score, course))
        
        # Sort by score and take the top results
        scored_courses.sort(key=lambda x: x[0], reverse=True)
        top_courses = [course for _, course in scored_courses[:limit]]
        
        formatted_courses = []
        for course in top_courses:
            formatted_courses.append({
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "category": course.category,
                "subcategory": course.subcategory,
                "thumbnail_url": course.thumbnail_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "instructor": (
                    {
                        "auth0_id": course.instructor.auth0_id,
                        "full_name": course.instructor.full_name,
                        "picture": course.instructor.picture
                    } if course.instructor else None
                )
            })
        
        return {
            "status": "success",
            "similar_courses": formatted_courses,
            "base_course_id": course_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching similar courses: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Get Course Statistics (Public)
# ----------------------------
@router.get("/stats")
async def get_course_statistics():
    """
    Get general statistics about the course catalog.
    Useful for homepage metrics or admin dashboards.
    """
    try:
        # Basic counts
        total_courses = await prisma.course.count(where={"is_published": True})
        total_enrollments = await prisma.enrollment.count()
        total_instructors = await prisma.user.count(where={"type": "INSTRUCTOR"})
        
        # Category distribution
        category_stats = await prisma.course.group_by(
            by=["category"],
            where={"is_published": True},
            _count={"category": True}
        )
        
        # Difficulty distribution
        difficulty_stats = await prisma.course.group_by(
            by=["difficulty_level"],
            where={"is_published": True},
            _count={"difficulty_level": True}
        )
        
        # Top rated courses count
        highly_rated_count = await prisma.course.count(
            where={
                "is_published": True,
                "rating": {"gte": 4.5}
            }
        )
        
        # Free vs paid distribution
        free_courses = await prisma.course.count(
            where={"is_published": True, "is_free": True}
        )
        paid_courses = total_courses - free_courses
        
        return {
            "status": "success",
            "statistics": {
                "overview": {
                    "total_courses": total_courses,
                    "total_enrollments": total_enrollments,
                    "total_instructors": total_instructors,
                    "highly_rated_courses": highly_rated_count
                },
                "categories": [
                    {"name": stat.category, "count": stat._count.category}
                    for stat in category_stats if stat.category
                ],
                "difficulty_levels": [
                    {"name": stat.difficulty_level, "count": stat._count.difficulty_level}
                    for stat in difficulty_stats if stat.difficulty_level
                ],
                "pricing": {
                    "free_courses": free_courses,
                    "paid_courses": paid_courses,
                    "free_percentage": round((free_courses / total_courses * 100), 1) if total_courses > 0 else 0
                }
            }
        }
        
    except Exception as e:
        logger.error("Error fetching course statistics: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Get Trending Courses
# ----------------------------
@router.get("/trending")
async def get_trending_courses(
    limit: int = Query(10, ge=1, le=20),
    timeframe: str = Query("week", regex="^(day|week|month)$")
):
    """
    Get trending courses based on recent enrollment activity.
    """
    try:
        from datetime import datetime, timedelta, timezone
        
        # Calculate timeframe
        now = datetime.now(timezone.utc)
        if timeframe == "day":
            since_date = now - timedelta(days=1)
        elif timeframe == "week":
            since_date = now - timedelta(weeks=1)
        else:  # month
            since_date = now - timedelta(days=30)
        
        # Get courses with recent enrollments
        recent_enrollments = await prisma.enrollment.find_many(
            where={
                "enrolled_at": {"gte": since_date},
                "course": {"is_published": True}
            },
            include={
                "course": {
                    "include": {
                        "instructor": True
                    }
                }
            }
        )
        
        # Count enrollments per course
        course_enrollment_counts = {}
        for enrollment in recent_enrollments:
            course_id = enrollment.course_id
            if course_id not in course_enrollment_counts:
                course_enrollment_counts[course_id] = {
                    "count": 0,
                    "course": enrollment.course
                }
            course_enrollment_counts[course_id]["count"] += 1
        
        # Sort by recent enrollment count and take top courses
        trending = sorted(
            course_enrollment_counts.values(),
            key=lambda x: x["count"],
            reverse=True
        )[:limit]
        
        formatted_courses = []
        for item in trending:
            course = item["course"]
            recent_enrollment_count = item["count"]
            
            formatted_courses.append({
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "difficulty_level": course.difficulty_level,
                "estimated_duration": course.estimated_duration,
                "category": course.category,
                "subcategory": course.subcategory,
                "thumbnail_url": course.thumbnail_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "instructor": (
                    {
                        "auth0_id": course.instructor.auth0_id,
                        "full_name": course.instructor.full_name,
                        "picture": course.instructor.picture
                    } if course.instructor else None
                ),
                "trending_stats": {
                    "recent_enrollments": recent_enrollment_count,
                    "timeframe": timeframe
                }
            })
        
        return {
            "status": "success",
            "trending_courses": formatted_courses,
            "metadata": {
                "timeframe": timeframe,
                "total_trending": len(formatted_courses)
            }
        }
        
    except Exception as e:
        logger.error("Error fetching trending courses: %s", e)
        raise HTTPException
