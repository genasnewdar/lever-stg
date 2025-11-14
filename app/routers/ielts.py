import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Literal
from fastapi import APIRouter, HTTPException, Security, status, Query
from pydantic import BaseModel, model_validator
from app.auth.auth import VerifyToken
from app.singleton import prisma
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from tenacity import retry, wait_exponential, stop_after_attempt

router = APIRouter(prefix="/api/ielts")
auth = VerifyToken()

# Set up logging
logger = logging.getLogger("ielts_student")
logger.setLevel(logging.INFO)

# Cloud Tasks configuration
base_url = os.getenv("API_BASE_URL")
FINISH_IELTS_TEST_URL = f"{base_url}/api/system/ielts/finish"

# ----------------------------
# Pydantic Models
# ----------------------------

class IeltsListeningResponseRequest(BaseModel):
    attempt_id: str
    question_id: str
    answer: str  # User's answer text

class IeltsReadingResponseRequest(BaseModel):
    attempt_id: str
    question_id: str
    answer: str  # User's answer text

class IeltsWritingResponseRequest(BaseModel):
    attempt_id: str
    task_id: str
    content: str  # User's written response
    word_count: Optional[int] = None

class IeltsSpeakingResponseRequest(BaseModel):
    attempt_id: str
    question_id: str
    audio_url: Optional[str] = None  # Recording URL
    transcript: Optional[str] = None  # Speech-to-text
    duration: Optional[int] = None  # seconds

# Batch submission models
class IeltsBatchResponseRequest(BaseModel):
    listening_responses: Optional[List[IeltsListeningResponseRequest]] = []
    reading_responses: Optional[List[IeltsReadingResponseRequest]] = []
    writing_responses: Optional[List[IeltsWritingResponseRequest]] = []
    speaking_responses: Optional[List[IeltsSpeakingResponseRequest]] = []

class IeltsModuleCompletionRequest(BaseModel):
    attempt_id: str
    module: Literal["LISTENING", "READING", "WRITING", "SPEAKING"]

# ----------------------------
# Helper Functions
# ----------------------------

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def schedule_finish_ielts_test(attempt_id: str, duration_seconds: int) -> str:
    """Schedule IELTS test auto-finish via Cloud Tasks"""
    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path("digital-heading-467012-a8", "us-central1", "ielts-finish-test-queue")
    
    scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(scheduled_time)
    
    payload = {"attempt_id": attempt_id}
    body = json.dumps(payload).encode()
    
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": FINISH_IELTS_TEST_URL,
            "headers": {
                "Content-Type": "application/json",
                "x-api-key": os.getenv("API_KEY")
            },
            "body": body,
        },
        "schedule_time": timestamp,
    }
    
    response = client.create_task(request={"parent": parent, "task": task})
    return response.name

def remove_sensitive_ielts_data(test_data: dict) -> dict:
    """Remove correct answers and sensitive data from IELTS test"""
    
    def clean_questions(questions: list):
        for question in questions:
            # Remove correct answers
            question.pop("correct_answer", None)
            
            # Clean options if present
            if "options" in question and isinstance(question["options"], list):
                for option in question["options"]:
                    option.pop("is_correct", None)
                    
            # Clean matching and additional data
            question.pop("matching_pairs", None)
            question.pop("matching_data", None)
    
    # Clean listening test
    if "listening_test" in test_data and test_data["listening_test"]:
        listening_test = test_data["listening_test"]
        if "sections" in listening_test:
            for section in listening_test["sections"]:
                if "questions" in section:
                    clean_questions(section["questions"])
    
    # Clean reading test
    if "reading_test" in test_data and test_data["reading_test"]:
        reading_test = test_data["reading_test"]
        if "passages" in reading_test:
            for passage in reading_test["passages"]:
                if "questions" in passage:
                    clean_questions(passage["questions"])
    
    return test_data

# ----------------------------
# IELTS Test Endpoints
# ----------------------------

@router.get("/tests")
async def list_ielts_tests(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    test_type: Optional[str] = Query(None, regex="^(ACADEMIC|GENERAL_TRAINING)$")
):
    """List available IELTS tests for students"""
    try:
        skip = (page - 1) * per_page
        
        where_clause = {"status": "ACTIVE"}
        if test_type:
            where_clause["test_type"] = test_type
        
        total_count = await prisma.ieltstest.count(where=where_clause)
        tests = await prisma.ieltstest.find_many(
            where=where_clause,
            skip=skip,
            take=per_page,
            order={"created_at": "desc"}
        )
        
        formatted_tests = [
            {
                "id": test.id,
                "title": test.title,
                "description": test.description,
                "test_type": test.test_type,
                "duration_minutes": test.duration_minutes,
                "is_practice": test.is_practice,
                "version": test.version
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

@router.get("/test/{test_id}")
async def get_ielts_test_for_student(test_id: str):
    """Get IELTS test details for student (without answers)"""
    try:
        test = await prisma.ieltstest.find_first(
            where={"id": test_id, "status": "ACTIVE"},
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
        
        # Remove sensitive data before returning
        clean_test = remove_sensitive_ielts_data(test.model_dump())
        return clean_test

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching IELTS test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/test/{test_id}/start")
async def start_ielts_test(
    test_id: str,
    auth_result: str = Security(auth.verify)
):
    """Start an IELTS test attempt"""
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(where={"auth0_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USER_NOT_FOUND"
            )
        
        # Check if test exists and is active
        test = await prisma.ieltstest.find_first(
            where={"id": test_id, "status": "ACTIVE"}
        )
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IELTS_TEST_NOT_FOUND"
            )
        
        # Check for existing in-progress attempt
        existing_attempt = await prisma.ieltstestattempt.find_first(
            where={
                "user_id": user.auth0_id,
                "test_id": test.id,
                "status": {"in": ["NOT_STARTED", "IN_PROGRESS", "LISTENING_COMPLETED", "READING_COMPLETED"]}
            }
        )
        
        if existing_attempt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IELTS_TEST_ALREADY_IN_PROGRESS"
            )
        
        # Create new attempt
        attempt = await prisma.ieltstestattempt.create(
            data={
                "user_id": user.auth0_id,
                "test_id": test.id,
                "status": "NOT_STARTED",
                "started_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=test.duration_minutes)
            }
        )
        
        # Schedule auto-finish
        try:
            task_name = schedule_finish_ielts_test(attempt.id, test.duration_minutes * 60)
            logger.info(f"Scheduled auto-finish task: {task_name}")
        except Exception as e:
            logger.error(f"Error scheduling auto-finish: {str(e)}")
            # Cancel the attempt if scheduling fails
            await prisma.ieltstestattempt.update(
                where={"id": attempt.id},
                data={"status": "CANCELLED"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FAILED_TO_START_TEST"
            )
        
        return attempt

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting IELTS test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# ----------------------------
# Response Submission Endpoints
# ----------------------------

@router.post("/response/listening")
async def submit_listening_response(
    payload: IeltsListeningResponseRequest,
    auth_result: str = Security(auth.verify)
):
    """Submit a listening response"""
    try:
        user_id = auth_result["sub"]
        
        # Validate attempt
        attempt = await prisma.ieltstestattempt.find_first(
            where={
                "id": payload.attempt_id,
                "user_id": user_id,
                "status": {"in": ["NOT_STARTED", "IN_PROGRESS"]}
            }
        )
        
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="INVALID_ATTEMPT"
            )
        
        # Upsert response
        response = await prisma.ieltslisteningresponse.upsert(
            where={
                "attempt_id_question_id": {
                    "attempt_id": payload.attempt_id,
                    "question_id": payload.question_id
                }
            },
            update={
                "answer": payload.answer
            },
            create={
                "attempt_id": payload.attempt_id,
                "question_id": payload.question_id,
                "answer": payload.answer
            }
        )
        
        # Update attempt status to IN_PROGRESS if it was NOT_STARTED
        if attempt.status == "NOT_STARTED":
            await prisma.ieltstestattempt.update(
                where={"id": attempt.id},
                data={"status": "IN_PROGRESS"}
            )
        
        return {"status": "success", "response": response}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting listening response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/response/reading")
async def submit_reading_response(
    payload: IeltsReadingResponseRequest,
    auth_result: str = Security(auth.verify)
):
    """Submit a reading response"""
    try:
        user_id = auth_result["sub"]
        
        # Validate attempt
        attempt = await prisma.ieltstestattempt.find_first(
            where={
                "id": payload.attempt_id,
                "user_id": user_id,
                "status": {"in": ["NOT_STARTED", "IN_PROGRESS", "LISTENING_COMPLETED"]}
            }
        )
        
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="INVALID_ATTEMPT"
            )
        
        # Upsert response
        response = await prisma.ieltsreadingresponse.upsert(
            where={
                "attempt_id_question_id": {
                    "attempt_id": payload.attempt_id,
                    "question_id": payload.question_id
                }
            },
            update={
                "answer": payload.answer
            },
            create={
                "attempt_id": payload.attempt_id,
                "question_id": payload.question_id,
                "answer": payload.answer
            }
        )
        
        return {"status": "success", "response": response}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting reading response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/response/writing")
async def submit_writing_response(
    payload: IeltsWritingResponseRequest,
    auth_result: str = Security(auth.verify)
):
    """Submit a writing response"""
    try:
        user_id = auth_result["sub"]
        
        # Validate attempt
        attempt = await prisma.ieltstestattempt.find_first(
            where={
                "id": payload.attempt_id,
                "user_id": user_id,
                "status": {"in": ["NOT_STARTED", "IN_PROGRESS", "LISTENING_COMPLETED", "READING_COMPLETED"]}
            }
        )
        
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="INVALID_ATTEMPT"
            )
        
        # Calculate word count if not provided
        word_count = payload.word_count
        if word_count is None:
            word_count = len(payload.content.split())
        
        # Upsert response
        response = await prisma.ieltswritingresponse.upsert(
            where={
                "attempt_id_task_id": {
                    "attempt_id": payload.attempt_id,
                    "task_id": payload.task_id
                }
            },
            update={
                "content": payload.content,
                "word_count": word_count
            },
            create={
                "attempt_id": payload.attempt_id,
                "task_id": payload.task_id,
                "content": payload.content,
                "word_count": word_count
            }
        )
        
        return {"status": "success", "response": response}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting writing response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )