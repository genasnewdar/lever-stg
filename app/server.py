from .secretenv import init_secrets
from dotenv import load_dotenv

init_secrets()
load_dotenv()

from fastapi import FastAPI
from contextlib import asynccontextmanager
from .singleton import prisma
from fastapi.middleware.cors import CORSMiddleware
from .routers import courses, health, test, user, ielts
from .routers.admin import (
  test as admin_test,
  course as admin_course,
  user as admin_user,
  ielts as admin_ielts
)
from .routers.admin import (
  employee as admin_employee
)
from .routers.system import (
    test as system_test,
    user as system_user,
    ielts as system_ielts,
    attendance as system_attendance
)
import logging
from .routers.system import agent_feedback as system_feedback

from .routers.course import (
    catalog,      # course catalog functionality
    content,      # course content delivery
    enrollment,   # course enrollment management
    progress,     # course progress tracking
    reviews       # course reviews and ratings
)


logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    try:
        await prisma.connect()
        yield # Application runs here
    except Exception as e:
        log.error(f"FastAPI startup error during init setup: {e}", exc_info=True)
        raise
        # yield # Allow app to start even if fails initially
    finally:
        await prisma.disconnect()
        log.info("FastAPI shutdown: Cleaning up resources...")

    
    
app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (you can restrict this if needed)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)


# system endpoints
app.include_router(system_test.router)
app.include_router(system_user.router)
app.include_router(system_feedback.router)
app.include_router(system_ielts.router)
app.include_router(system_attendance.router)

# admin endpoints
app.include_router(admin_test.router)
app.include_router(admin_course.router)
app.include_router(admin_user.router)
app.include_router(admin_ielts.router)
app.include_router(admin_employee.router)

# user endpoints
app.include_router(health.router)
app.include_router(test.router)
app.include_router(courses.router)
app.include_router(user.router)
app.include_router(ielts.router)

# Course-specific endpoints (if separated into modules)
app.include_router(catalog.router)      # Course catalog/browsing
app.include_router(content.router)      # Course content delivery  
app.include_router(enrollment.router)   # Course enrollment
app.include_router(progress.router)     # Progress tracking
app.include_router(reviews.router)      # Course reviews and ratings


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
