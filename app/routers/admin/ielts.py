import time
import json
import logging
from fastapi import APIRouter, HTTPException, Security, status
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/admin/ielts")
auth = VerifyToken()

# Set up logging
logger = logging.getLogger("admin_ielts")
logger.setLevel(logging.INFO)

# ----------------------------
# IELTS Pydantic Models for Payload
# ----------------------------

# Listening Test Models
class IeltsListeningOptionCreate(BaseModel):
    label: str
    text: str
    is_correct: Optional[bool] = False
    order: int

class IeltsListeningQuestionCreate(BaseModel):
    question_number: int  # 1-40
    question_text: Optional[str] = None
    question_type: str  # IeltsQuestionType enum value
    points: Optional[float] = 1.0
    audio_start_time: Optional[int] = None  # seconds
    audio_end_time: Optional[int] = None
    correct_answer: Optional[str] = None  # For short answers
    options: Optional[List[IeltsListeningOptionCreate]] = []  # For multiple choice
    matching_pairs: Optional[dict] = None  # For matching questions
    additional_data: Optional[dict] = None

class IeltsListeningSectionCreate(BaseModel):
    section_number: int  # 1, 2, 3, 4
    title: str
    context: Optional[str] = None  # Description of situation
    audio_url: Optional[str] = None
    audio_start_time: Optional[int] = None
    audio_end_time: Optional[int] = None
    instructions: Optional[str] = None
    questions: List[IeltsListeningQuestionCreate] = []

class IeltsListeningTestCreate(BaseModel):
    duration_minutes: Optional[int] = 40
    instructions: Optional[str] = None
    audio_url: Optional[str] = None  # Main audio file
    sections: List[IeltsListeningSectionCreate] = []

# Reading Test Models
class IeltsReadingOptionCreate(BaseModel):
    label: str
    text: str
    is_correct: Optional[bool] = False
    order: int

class IeltsReadingQuestionCreate(BaseModel):
    question_number: int  # 1-40
    question_text: Optional[str] = None
    question_type: str  # IeltsQuestionType enum value
    points: Optional[float] = 1.0
    instructions: Optional[str] = None
    correct_answer: Optional[str] = None
    options: Optional[List[IeltsReadingOptionCreate]] = []
    matching_data: Optional[dict] = None
    additional_data: Optional[dict] = None

class IeltsReadingPassageCreate(BaseModel):
    passage_number: int  # 1, 2, 3
    title: str
    content: str  # The reading passage
    word_count: Optional[int] = None
    source: Optional[str] = None
    questions: List[IeltsReadingQuestionCreate] = []

class IeltsReadingTestCreate(BaseModel):
    duration_minutes: Optional[int] = 60
    instructions: Optional[str] = None
    passages: List[IeltsReadingPassageCreate] = []

# Writing Test Models
class IeltsWritingTaskCreate(BaseModel):
    task_number: int  # 1 or 2
    task_type: str  # TASK_1_ACADEMIC, TASK_1_GENERAL, TASK_2
    title: str
    prompt: str  # The writing prompt
    min_words: Optional[int] = 150
    suggested_time: Optional[int] = 20  # minutes
    visual_content: Optional[str] = None  # URL for charts/graphs

class IeltsWritingTestCreate(BaseModel):
    duration_minutes: Optional[int] = 60
    instructions: Optional[str] = None
    tasks: List[IeltsWritingTaskCreate] = []

# Speaking Test Models
class IeltsSpeakingQuestionCreate(BaseModel):
    question_text: str
    question_type: str  # PART_1, PART_2, PART_3
    preparation_time: Optional[int] = None  # seconds
    speaking_time: Optional[int] = None  # seconds
    cue_card: Optional[str] = None  # For Part 2
    follow_up_notes: Optional[str] = None

class IeltsSpeakingPartCreate(BaseModel):
    part_number: int  # 1, 2, 3
    title: str
    duration_minutes: int
    instructions: Optional[str] = None
    questions: List[IeltsSpeakingQuestionCreate] = []

class IeltsSpeakingTestCreate(BaseModel):
    duration_minutes: Optional[int] = 15
    instructions: Optional[str] = None
    parts: List[IeltsSpeakingPartCreate] = []

# Main IELTS Test Creation Model
class AdminCreateIeltsTestRequest(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = "DRAFT"
    duration_minutes: Optional[int] = 180
    is_practice: Optional[bool] = True
    version: Optional[str] = None
    
    # Test components (all optional)
    listening_test: Optional[IeltsListeningTestCreate] = None
    reading_test: Optional[IeltsReadingTestCreate] = None
    writing_test: Optional[IeltsWritingTestCreate] = None
    speaking_test: Optional[IeltsSpeakingTestCreate] = None

# ----------------------------
# Helper Functions
# ----------------------------
def wrap_create_field(data: dict, field: str):
    """Wrap nested create fields for Prisma"""
    if field in data and isinstance(data[field], list):
        data[field] = {"create": data[field]}

def process_nested_questions(questions_list: list):
    """Process questions with options for nested creation"""
    for question in questions_list:
        wrap_create_field(question, "options")
        
        # Handle JSON fields
        if "matching_pairs" in question and question["matching_pairs"]:
            question["matching_pairs"] = json.dumps(question["matching_pairs"])
        if "matching_data" in question and question["matching_data"]:
            question["matching_data"] = json.dumps(question["matching_data"])
        if "additional_data" in question and question["additional_data"]:
            question["additional_data"] = json.dumps(question["additional_data"])

# ----------------------------
# Admin Create IELTS Test Endpoint
# ----------------------------
@router.post("/test")
async def create_ielts_test(
    payload: AdminCreateIeltsTestRequest,
    auth_result: str = Security(auth.verify)
):
    try:
        # Convert payload to dict
        test_data = payload.model_dump(exclude_none=True)
        
        # Process listening test if provided
        if "listening_test" in test_data:
            listening_data = test_data["listening_test"]
            if "sections" in listening_data:
                for section in listening_data["sections"]:
                    if "questions" in section:
                        process_nested_questions(section["questions"])
                    wrap_create_field(section, "questions")
                wrap_create_field(listening_data, "sections")
        
        # Process reading test if provided
        if "reading_test" in test_data:
            reading_data = test_data["reading_test"]
            if "passages" in reading_data:
                for passage in reading_data["passages"]:
                    if "questions" in passage:
                        process_nested_questions(passage["questions"])
                    wrap_create_field(passage, "questions")
                wrap_create_field(reading_data, "passages")
        
        # Process writing test if provided
        if "writing_test" in test_data:
            writing_data = test_data["writing_test"]
            wrap_create_field(writing_data, "tasks")
        
        # Process speaking test if provided
        if "speaking_test" in test_data:
            speaking_data = test_data["speaking_test"]
            if "parts" in speaking_data:
                for part in speaking_data["parts"]:
                    wrap_create_field(part, "questions")
                wrap_create_field(speaking_data, "parts")

        # Create the IELTS test
        created_test = await prisma.ieltstest.create(data=test_data)
        
        logger.info(f"Created IELTS test: {created_test.id}")
        return created_test

    except Exception as e:
        logger.error(f"Error creating IELTS test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Get IELTS Test (Admin View)
# ----------------------------
@router.get("/test/{test_id}")
async def get_ielts_test_admin(
    test_id: str,
    auth_result: str = Security(auth.verify)
):
    try:
        test = await prisma.ieltstest.find_first(
            where={"id": test_id},
            include={
                "listening_test": {
                    "include": {
                        "sections": {
                            "include": {
                                "questions": {
                                    "include": {"options": True}
                                }
                            }
                        }
                    }
                },
                "reading_test": {
                    "include": {
                        "passages": {
                            "include": {
                                "questions": {
                                    "include": {"options": True}
                                }
                            }
                        }
                    }
                },
                "writing_test": {
                    "include": {"tasks": True}
                },
                "speaking_test": {
                    "include": {
                        "parts": {
                            "include": {"questions": True}
                        }
                    }
                }
            }
        )
        
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IELTS_TEST_NOT_FOUND"
            )
        
        return test

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching IELTS test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# List IELTS Tests (Admin)
# ----------------------------
@router.get("/tests")
async def list_ielts_tests_admin(
    auth_result: str = Security(auth.verify),
    page: int = 1,
    per_page: int = 10
):
    try:
        skip = (page - 1) * per_page
        
        total_count = await prisma.ieltstest.count()
        tests = await prisma.ieltstest.find_many(
            skip=skip,
            take=per_page,
            order={"created_at": "desc"}
        )
        
        # Format for admin list view
        formatted_tests = [
            {
                "id": test.id,
                "title": test.title,
                "status": test.status,
                "is_practice": test.is_practice,
                "duration_minutes": test.duration_minutes,
                "created_at": test.created_at,
                "published_at": test.published_at
            }
            for test in tests
        ]
        
        return {
            "tests": formatted_tests,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }

    except Exception as e:
        logger.error(f"Error listing IELTS tests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Update IELTS Test Status (Publish/Archive)
# ----------------------------
@router.patch("/test/{test_id}/status")
async def update_ielts_test_status(
    test_id: str,
    status_update: dict,
    auth_result: str = Security(auth.verify)
):
    try:
        new_status = status_update.get("status")
        if new_status not in ["DRAFT", "ACTIVE", "ARCHIVED", "INACTIVE"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status"
            )
        
        update_data = {"status": new_status}
        if new_status == "ACTIVE":
            update_data["published_at"] = datetime.now(timezone.utc)
        
        updated_test = await prisma.ieltstest.update(
            where={"id": test_id},
            data=update_data
        )
        
        return updated_test

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating IELTS test status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )