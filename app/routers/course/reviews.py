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
logger = logging.getLogger("course_reviews")
logger.setLevel(logging.INFO)

# Pydantic models
class ReviewCreate(BaseModel):
    course_id: str
    rating: int
    review_text: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v
    
    @validator('review_text')
    def validate_review_text(cls, v):
        if v is not None and len(v.strip()) == 0:
            return None
        if v is not None and len(v) > 2000:
            raise ValueError('Review text cannot exceed 2000 characters')
        return v

class ReviewUpdate(BaseModel):
    rating: Optional[int] = None
    review_text: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v):
        if v is not None and (v < 1 or v > 5):
            raise ValueError('Rating must be between 1 and 5')
        return v
    
    @validator('review_text')
    def validate_review_text(cls, v):
        if v is not None and len(v) > 2000:
            raise ValueError('Review text cannot exceed 2000 characters')
        return v

class ReviewResponse(BaseModel):
    id: str
    rating: int
    review_text: Optional[str]
    created_at: datetime
    user: Dict[str, Any]
    course_title: str
    is_helpful: Optional[bool] = None  # If current user found it helpful

class CourseRatingStats(BaseModel):
    average_rating: float
    total_reviews: int
    rating_distribution: Dict[str, int]  # "1": count, "2": count, etc.

# ----------------------------
# Create Course Review
# ----------------------------
@router.post("/{course_id}/reviews")
async def create_course_review(
    course_id: str,
    review_data: ReviewCreate,
    auth_result: str = Security(auth.verify)
):
    """Create a review for a course"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and is published
        course = await prisma.course.find_first(
            where={"id": course_id, "is_published": True}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Check if user is enrolled in the course
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        if not enrollment:
            raise Exception("ENROLLMENT_REQUIRED")
        
        # Check if user already reviewed this course
        existing_review = await prisma.coursereview.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id
            }
        )
        
        if existing_review:
            raise Exception("REVIEW_ALREADY_EXISTS")
        
        # Create the review
        new_review = await prisma.coursereview.create(
            data={
                "user_id": user.auth0_id,
                "course_id": course_id,
                "rating": review_data.rating,
                "review_text": review_data.review_text,
                "created_at": datetime.now(timezone.utc)
            }
        )
        
        # Update course rating statistics
        await _update_course_rating_stats(course_id)
        
        return {
            "status": "success",
            "review": {
                "id": new_review.id,
                "rating": new_review.rating,
                "review_text": new_review.review_text,
                "created_at": new_review.created_at,
                "user": {
                    "auth0_id": user.auth0_id,
                    "full_name": user.full_name,
                    "picture": user.picture
                },
                "course_title": course.title
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating course review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Course Reviews
# ----------------------------
@router.get("/{course_id}/reviews")
async def get_course_reviews(
    course_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    rating_filter: Optional[int] = Query(None, ge=1, le=5),
    sort_by: str = Query("created_at", regex="^(created_at|rating|helpful)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    auth_result: str = Security(auth.verify)
):
    """Get reviews for a course with filtering and pagination"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and is published
        course = await prisma.course.find_first(
            where={"id": course_id, "is_published": True}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        skip = (page - 1) * per_page
        
        # Build where clause
        where_clause = {"course_id": course_id}
        if rating_filter:
            where_clause["rating"] = rating_filter
        
        total_count = await prisma.coursereview.count(where=where_clause)
        
        # Build order clause
        order_clause = {sort_by: sort_order}
        
        reviews = await prisma.coursereview.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order=order_clause,
            include={
                "user": {
                    "select": {
                        "auth0_id": True,
                        "full_name": True,
                        "picture": True,
                        "type": True
                    }
                }
            }
        )
        
        formatted_reviews = []
        for review in reviews:
            # Check if current user found this review helpful (if we had a helpful system)
            is_helpful = None  # Placeholder for future helpful/not helpful feature
            
            formatted_reviews.append({
                "id": review.id,
                "rating": review.rating,
                "review_text": review.review_text,
                "created_at": review.created_at,
                "user": {
                    "auth0_id": review.user.auth0_id,
                    "full_name": review.user.full_name,
                    "picture": review.user.picture,
                    "type": review.user.type,
                    "is_verified_purchase": True  # Since enrollment is required
                },
                "is_helpful": is_helpful,
                "is_own_review": review.user_id == user.auth0_id
            })
        
        # Get rating statistics
        rating_stats = await _get_course_rating_stats(course_id)
        
        return {
            "status": "success",
            "reviews": formatted_reviews,
            "rating_stats": rating_stats,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching course reviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Update Course Review
# ----------------------------
@router.put("/reviews/{review_id}")
async def update_course_review(
    review_id: str,
    review_update: ReviewUpdate,
    auth_result: str = Security(auth.verify)
):
    """Update user's own course review"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get the review
        review = await prisma.coursereview.find_first(
            where={"id": review_id},
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "is_published": True
                    }
                }
            }
        )
        
        if not review or not review.course.is_published:
            raise Exception("REVIEW_NOT_FOUND")
        
        # Check if user owns this review
        if review.user_id != user.auth0_id:
            raise Exception("UNAUTHORIZED_ACCESS")
        
        # Prepare update data
        update_data = {}
        if review_update.rating is not None:
            update_data["rating"] = review_update.rating
        if review_update.review_text is not None:
            update_data["review_text"] = review_update.review_text
        
        if not update_data:
            raise Exception("NO_UPDATE_DATA")
        
        # Update the review
        updated_review = await prisma.coursereview.update(
            where={"id": review_id},
            data=update_data
        )
        
        # Update course rating statistics if rating changed
        if review_update.rating is not None:
            await _update_course_rating_stats(review.course_id)
        
        return {
            "status": "success",
            "review": {
                "id": updated_review.id,
                "rating": updated_review.rating,
                "review_text": updated_review.review_text,
                "created_at": updated_review.created_at,
                "course_title": review.course.title
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating course review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Delete Course Review
# ----------------------------
@router.delete("/reviews/{review_id}")
async def delete_course_review(
    review_id: str,
    auth_result: str = Security(auth.verify)
):
    """Delete user's own course review"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Get the review
        review = await prisma.coursereview.find_first(
            where={"id": review_id}
        )
        
        if not review:
            raise Exception("REVIEW_NOT_FOUND")
        
        # Check if user owns this review or is admin
        if review.user_id != user.auth0_id and user.type != "ADMIN":
            raise Exception("UNAUTHORIZED_ACCESS")
        
        # Delete the review
        await prisma.coursereview.delete(
            where={"id": review_id}
        )
        
        # Update course rating statistics
        await _update_course_rating_stats(review.course_id)
        
        return {
            "status": "success",
            "message": "Review deleted successfully"
        }
        
    except Exception as e:
        logger.error(f"Error deleting course review: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get My Reviews
# ----------------------------
@router.get("/my-reviews")
async def get_my_reviews(
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50)
):
    """Get all reviews by the current user"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        skip = (page - 1) * per_page
        
        total_count = await prisma.coursereview.count(
            where={"user_id": user.auth0_id}
        )
        
        reviews = await prisma.coursereview.find_many(
            where={"user_id": user.auth0_id},
            skip=skip,
            take=per_page,
            order={"created_at": "desc"},
            include={
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "short_title": True,
                        "thumbnail_url": True,
                        "category": True,
                        "instructor": {
                            "select": {
                                "auth0_id": True,
                                "full_name": True
                            }
                        }
                    }
                }
            }
        )
        
        formatted_reviews = []
        for review in reviews:
            formatted_reviews.append({
                "id": review.id,
                "rating": review.rating,
                "review_text": review.review_text,
                "created_at": review.created_at,
                "course": {
                    "id": review.course.id,
                    "title": review.course.title,
                    "short_title": review.course.short_title,
                    "thumbnail_url": review.course.thumbnail_url,
                    "category": review.course.category,
                    "instructor": review.course.instructor
                }
            })
        
        return {
            "status": "success",
            "reviews": formatted_reviews,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching user reviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Course Rating Statistics
# ----------------------------
@router.get("/{course_id}/rating-stats")
async def get_course_rating_statistics(course_id: str):
    """Get detailed rating statistics for a course (public endpoint)"""
    try:
        # Check if course exists and is published
        course = await prisma.course.find_first(
            where={"id": course_id, "is_published": True}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        rating_stats = await _get_course_rating_stats(course_id)
        
        return {
            "status": "success",
            "course_id": course_id,
            "rating_stats": rating_stats
        }
        
    except Exception as e:
        logger.error(f"Error fetching course rating stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Check if User Can Review Course
# ----------------------------
@router.get("/{course_id}/can-review")
async def check_can_review_course(
    course_id: str,
    auth_result: str = Security(auth.verify)
):
    """Check if current user can review a course"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={"auth0_id": user_id}
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        # Check if course exists and is published
        course = await prisma.course.find_first(
            where={"id": course_id, "is_published": True}
        )
        if not course:
            raise Exception("COURSE_NOT_FOUND")
        
        # Check enrollment
        enrollment = await prisma.enrollment.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id,
                "status": {"in": ["ACTIVE", "COMPLETED"]}
            }
        )
        
        # Check existing review
        existing_review = await prisma.coursereview.find_first(
            where={
                "user_id": user.auth0_id,
                "course_id": course_id
            }
        )
        
        can_review = enrollment is not None and existing_review is None
        reason = None
        
        if not enrollment:
            reason = "NOT_ENROLLED"
        elif existing_review:
            reason = "ALREADY_REVIEWED"
        
        return {
            "status": "success",
            "can_review": can_review,
            "reason": reason,
            "existing_review": {
                "id": existing_review.id,
                "rating": existing_review.rating,
                "review_text": existing_review.review_text,
                "created_at": existing_review.created_at
            } if existing_review else None
        }
        
    except Exception as e:
        logger.error(f"Error checking review eligibility: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Top Rated Courses
# ----------------------------
@router.get("/top-rated")
async def get_top_rated_courses(
    limit: int = Query(10, ge=1, le=50),
    category: Optional[str] = Query(None),
    min_reviews: int = Query(5, ge=1)
):
    """Get top-rated courses with minimum review threshold"""
    try:
        where_clause = {
            "is_published": True,
            "rating_count": {"gte": min_reviews}
        }
        
        if category:
            where_clause["category"] = category
        
        courses = await prisma.course.find_many(
            where=where_clause,
            take=limit,
            order=[
                {"rating": "desc"},
                {"rating_count": "desc"}
            ],
            include={
                "instructor": {
                    "select": {
                        "auth0_id": True,
                        "full_name": True,
                        "picture": True
                    }
                }
            }
        )
        
        formatted_courses = []
        for course in courses:
            formatted_courses.append({
                "id": course.id,
                "title": course.title,
                "short_title": course.short_title,
                "description": course.description,
                "category": course.category,
                "subcategory": course.subcategory,
                "difficulty_level": course.difficulty_level,
                "thumbnail_url": course.thumbnail_url,
                "price": float(course.price) if course.price else None,
                "is_free": course.is_free,
                "rating": course.rating,
                "rating_count": course.rating_count,
                "enrollment_count": course.enrollment_count,
                "instructor": course.instructor
            })
        
        return {
            "status": "success",
            "top_rated_courses": formatted_courses,
            "criteria": {
                "minimum_reviews": min_reviews,
                "category_filter": category,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching top-rated courses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get Recent Reviews
# ----------------------------
@router.get("/recent-reviews")
async def get_recent_reviews(
    limit: int = Query(10, ge=1, le=50),
    days: int = Query(30, ge=1, le=365)
):
    """Get recent reviews across all courses"""
    try:
        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        reviews = await prisma.coursereview.find_many(
            where={
                "created_at": {"gte": since_date},
                "course": {"is_published": True}
            },
            take=limit,
            order={"created_at": "desc"},
            include={
                "user": {
                    "select": {
                        "auth0_id": True,
                        "full_name": True,
                        "picture": True
                    }
                },
                "course": {
                    "select": {
                        "id": True,
                        "title": True,
                        "short_title": True,
                        "thumbnail_url": True,
                        "category": True
                    }
                }
            }
        )
        
        formatted_reviews = []
        for review in reviews:
            formatted_reviews.append({
                "id": review.id,
                "rating": review.rating,
                "review_text": review.review_text,
                "created_at": review.created_at,
                "user": review.user,
                "course": review.course
            })
        
        return {
            "status": "success",
            "recent_reviews": formatted_reviews,
            "timeframe_days": days
        }
        
    except Exception as e:
        logger.error(f"Error fetching recent reviews: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Helper Functions
# ----------------------------
async def _update_course_rating_stats(course_id: str):
    """Update course rating and rating count based on reviews"""
    try:
        # Get all reviews for the course
        reviews = await prisma.coursereview.find_many(
            where={"course_id": course_id}
        )
        
        if not reviews:
            # No reviews, set defaults
            await prisma.course.update(
                where={"id": course_id},
                data={
                    "rating": 0,
                    "rating_count": 0
                }
            )
            return
        
        # Calculate average rating
        total_rating = sum(review.rating for review in reviews)
        average_rating = round(total_rating / len(reviews), 1)
        
        # Update course
        await prisma.course.update(
            where={"id": course_id},
            data={
                "rating": average_rating,
                "rating_count": len(reviews)
            }
        )
        
    except Exception as e:
        logger.error(f"Error updating course rating stats: {str(e)}")

async def _get_course_rating_stats(course_id: str) -> Dict[str, Any]:
    """Get detailed rating statistics for a course"""
    try:
        # Get all reviews for the course
        reviews = await prisma.coursereview.find_many(
            where={"course_id": course_id}
        )
        
        if not reviews:
            return {
                "average_rating": 0,
                "total_reviews": 0,
                "rating_distribution": {
                    "1": 0, "2": 0, "3": 0, "4": 0, "5": 0
                }
            }
        
        # Calculate statistics
        total_reviews = len(reviews)
        total_rating = sum(review.rating for review in reviews)
        average_rating = round(total_rating / total_reviews, 1)
        
        # Calculate rating distribution
        rating_distribution = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for review in reviews:
            rating_distribution[str(review.rating)] += 1
        
        return {
            "average_rating": average_rating,
            "total_reviews": total_reviews,
            "rating_distribution": rating_distribution
        }
        
    except Exception as e:
        logger.error(f"Error getting course rating stats: {str(e)}")
        return {
            "average_rating": 0,
            "total_reviews": 0,
            "rating_distribution": {
                "1": 0, "2": 0, "3": 0, "4": 0, "5": 0
            }
        }