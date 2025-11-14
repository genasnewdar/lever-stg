from fastapi import APIRouter
from .course.catalog import router as catalog_router
from .course.enrollment import router as enrollment_router
from .course.progress import router as progress_router
from .course.content import router as content_router
from .course.reviews import router as reviews_router

router = APIRouter()

router.include_router(catalog_router)
router.include_router(enrollment_router)
router.include_router(progress_router)
router.include_router(content_router)
router.include_router(reviews_router)