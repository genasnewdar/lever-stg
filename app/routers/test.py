import json
import os
import logging
from fastapi import APIRouter, HTTPException, Security, status, Query
from app.auth.auth import VerifyToken
from app.singleton import prisma
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from datetime import datetime, timedelta, timezone
from tenacity import retry, wait_exponential, stop_after_attempt
from pydantic import BaseModel, model_validator
from typing import Optional, Dict, Literal
from app.services.grader import grade_test, gather_insight_data, get_clean_feedback_payload
from app.services.ai import grade_yesh

from typing import List, Optional


router = APIRouter(prefix="/api/test")
auth = VerifyToken()

# Set up logging (configure handlers/levels as needed)
logger = logging.getLogger("test")
logger.setLevel(logging.INFO)


base_url = os.getenv("API_BASE_URL")
FINISH_TEST_URL = f"{base_url}/api/system/test/finish"

@retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
def schedule_finish_test(test_attempt_id: str, test_duration_seconds: int) -> str:
    """
    Creates a Cloud Task to trigger the finish-test endpoint after the specified delay.
    Returns the name of the created task.
    """
    client = tasks_v2.CloudTasksClient()
    # Construct the fully qualified queue name.
    parent = client.queue_path("digital-heading-467012-a8", "us-central1", "lever-finish-test-queue-stg")

    # Calculate the schedule time as the current UTC time plus the delay.
    scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=test_duration_seconds)
    timestamp = timestamp_pb2.Timestamp()
    timestamp.FromDatetime(scheduled_time)

    # Prepare the payload; here we pass the test attempt ID
    payload = {"test_attempt_id": test_attempt_id}
    payload_str = json.dumps(payload)
    # Cloud Tasks expects the body in base64-encoded bytes
    body = payload_str.encode()

    # Construct the task
    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": FINISH_TEST_URL,
            "headers": {
                "Content-Type": "application/json",
                "x-api-key": os.getenv("API_KEY")
            },
            "body": body,
        },
        "schedule_time": timestamp,
    }

    # Create and return the task name.
    response = client.create_task(request={"parent": parent, "task": task})
    return response.name

# ----------------------------
# Student Start Test Endpoint
# ----------------------------
@router.post("/{id}/start")
async def start_test(id: str, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={
                "auth0_id": user_id
            }
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        test = await prisma.test.find_first(
            where={
                "id": id,
                "is_active": True
            }
        )
        if not test:
            raise Exception("TEST_NOT_FOUND")
        
        
        test_attempt_check = await prisma.testattempt.find_first(
            where={
                "user_id": user.auth0_id,
                "test_id": test.id,
                "status": "IN_PROGRESS"
            }
        )
        
        if test_attempt_check:
            raise Exception("TEST_ALREADY_IN_PROGRESS")
        
        test_attempt = await prisma.testattempt.create(
            data={
                "user_id": user.auth0_id,
                "test_id": test.id,
                "started_at": datetime.now(timezone.utc),
                "due_at": datetime.now(timezone.utc) + timedelta(minutes=test.duration),
            }
        )
        
        try:
            schedule_finish_test(test_attempt.id, test.duration * 60)
        except Exception as e:
            logger.error(f"Error scheduling finish test task: {str(e)}")
            test_attempt = await prisma.testattempt.update(
                where={
                    "id": test_attempt.id
                },
                data={
                    "status": "CANCELED_BY_SYSTEM",
                    "finish_id": "SYSTEM"
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="START_TEST_FAILED"
            )

        return test_attempt
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error starting test: {str(e)}"
        )
        
        
# ----------------------------
# Student Submit Question Response Endpoint
# ----------------------------

class SubmitQuestionResponseRequest(BaseModel):
    attempt_id: str
    question_id: str
    question_type: Literal[
        "MULTIPLE_CHOICE", 
        "MATCHING"
    ]
    # Optional fields: which will be conditionally required.
    selected_option_id: Optional[str] = None
    additional_data: Optional[Dict] = None
    
    @model_validator(mode="after")
    def check_required_fields(self):
        # Ensure that both fields are not set simultaneously.
        if self.selected_option_id is not None and self.additional_data is not None:
            raise ValueError("Only one of selected_option_id or additional_data should be set.")
        
        # Conditional validations based on question type.
        if self.question_type == "MULTIPLE_CHOICE":
            if not self.selected_option_id:
                raise ValueError("For MULTIPLE_CHOICE questions, selected_option_id is required.")
        elif self.question_type == "MATCHING":
            if not self.additional_data:
                raise ValueError("For MATCHING questions, additional_data is required.")
                
        return self


@router.post("/response/submit")
async def submit_question_response(payload: SubmitQuestionResponseRequest, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={
                "auth0_id": user_id
            }
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        attempt = await prisma.testattempt.find_first(
            where={
                "id": payload.attempt_id,
                "user_id": user.auth0_id
            }
        )
        
        if not attempt:
            raise Exception("TEST_ATTEMPT_NOT_FOUND")
        
        if attempt.status != "IN_PROGRESS":
            raise Exception("TEST_ATTEMPT_NOT_IN_PROGRESS")
        
        
        question = await prisma.question.find_first(
            where={
                "id": payload.question_id
            }
        )
        
        if not question:
            raise Exception("QUESTION_NOT_FOUND")

        if question.type != payload.question_type:
            raise Exception("QUESTION_TYPE_MISMATCH")
        
        
        if payload.question_type == "MULTIPLE_CHOICE":
            option = await prisma.option.find_first(
                where={
                    "id": payload.selected_option_id,
                    "questionId": payload.question_id
                }
            )
            
            if not option:
                raise Exception("OPTION_NOT_FOUND")
        
        # Check if a response record already exists based on attempt_id and question_id.
        existing_response = await prisma.response.find_first(
            where={
                "attempt_id": payload.attempt_id,
                "question_id": payload.question_id
            }
        )

        data = {
            "attempt_id": payload.attempt_id,
            "question_id": payload.question_id
        }

        if payload.selected_option_id is not None:
            data["selected_option"] = payload.selected_option_id
        if payload.additional_data is not None:
            data["additional_data"] = payload.additional_data

        if existing_response:
            updated_response = await prisma.response.update(
                where={"id": existing_response.id},
                data=data
            )
            return {"status": "success", "response": updated_response}
        else:
            created_response = await prisma.response.create(data=data)
            return {"status": "success", "response": created_response}

    except Exception as e:
        logger.error(f"Error upserting question response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
class SubmitQuestionResponseRequest(BaseModel):
    attempt_id: str
    question_id: str
    question_type: str
    selected_option_id: Optional[str] = None
    additional_data: Optional[dict] = None # Assuming this field exists based on usage

# Define the response model for each individual result within the batch
class SubmitResponseResult(BaseModel):
    question_id: str
    status: str # "success" or "failed"
    message: Optional[str] = None
    response_id: Optional[str] = None # ID of the created/updated response record

# --- API Endpoint ---
@router.post("/response/submit_batch") # Renamed for clarity to indicate batch processing
async def submit_question_response_batch(payload: List[SubmitQuestionResponseRequest], auth_result: str = Security(auth.verify)):
    """
    Submits multiple question responses for an ongoing test attempt.
    Each response within the provided list is processed individually.
    """
    user_id = auth_result["sub"]
    results: List[SubmitResponseResult] = [] # To collect results for each item in the batch

    try:
        # Fetch the user once for the entire batch request
        user = await prisma.user.find_first(
            where={
                "auth0_id": user_id
            }
        )
        if not user:
            # If the user is not found, the entire batch request is unauthorized
            logger.error(f"Authentication error: User with auth0_id {user_id} not found.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="USER_NOT_FOUND"
            )

        # Process each question response in the payload list
        for item_payload in payload:
            try:
                # Validate the test attempt for the current item
                attempt = await prisma.testattempt.find_first(
                    where={
                        "id": item_payload.attempt_id,
                        "user_id": user.auth0_id # Ensure the attempt belongs to the user
                    }
                )

                if not attempt:
                    results.append(SubmitResponseResult(
                        question_id=item_payload.question_id,
                        status="failed",
                        message="TEST_ATTEMPT_NOT_FOUND or unauthorized for this user"
                    ))
                    continue # Skip to the next item in the batch

                if attempt.status != "IN_PROGRESS":
                    results.append(SubmitResponseResult(
                        question_id=item_payload.question_id,
                        status="failed",
                        message="TEST_ATTEMPT_NOT_IN_PROGRESS"
                    ))
                    continue # Skip to the next item in the batch

                # Validate the question for the current item
                question = await prisma.question.find_first(
                    where={
                        "id": item_payload.question_id
                    }
                )

                if not question:
                    results.append(SubmitResponseResult(
                        question_id=item_payload.question_id,
                        status="failed",
                        message="QUESTION_NOT_FOUND"
                    ))
                    continue # Skip to the next item in the batch

                if question.type != item_payload.question_type:
                    results.append(SubmitResponseResult(
                        question_id=item_payload.question_id,
                        status="failed",
                        message="QUESTION_TYPE_MISMATCH"
                    ))
                    continue # Skip to the next item in the batch

                # Handle specific question types (e.g., MULTIPLE_CHOICE)
                if item_payload.question_type == "MULTIPLE_CHOICE":
                    # Ensure selected_option_id is provided for MCQs and is valid
                    if not item_payload.selected_option_id:
                         results.append(SubmitResponseResult(
                            question_id=item_payload.question_id,
                            status="failed",
                            message="selected_option_id is required for MULTIPLE_CHOICE"
                        ))
                         continue

                    option = await prisma.option.find_first(
                        where={
                            "id": item_payload.selected_option_id,
                            "questionId": item_payload.question_id
                        }
                    )

                    if not option:
                        results.append(SubmitResponseResult(
                            question_id=item_payload.question_id,
                            status="failed",
                            message="OPTION_NOT_FOUND for this question"
                        ))
                        continue # Skip to the next item in the batch

                # Prepare data for upserting the response
                data = {
                    "attempt_id": item_payload.attempt_id,
                    "question_id": item_payload.question_id
                }

                if item_payload.selected_option_id is not None:
                    data["selected_option"] = item_payload.selected_option_id
                if item_payload.additional_data is not None:
                    data["additional_data"] = item_payload.additional_data

                # Check if a response record already exists for this question in this attempt
                existing_response = await prisma.response.find_first(
                    where={
                        "attempt_id": item_payload.attempt_id,
                        "question_id": item_payload.question_id
                    }
                )

                if existing_response:
                    # Update existing response
                    updated_response = await prisma.response.update(
                        where={"id": existing_response.id},
                        data=data
                    )
                    results.append(SubmitResponseResult(
                        question_id=item_payload.question_id,
                        status="success",
                        response_id=updated_response.id,
                        message="Response updated successfully"
                    ))
                else:
                    # Create new response
                    created_response = await prisma.response.create(data=data)
                    results.append(SubmitResponseResult(
                        question_id=item_payload.question_id,
                        status="success",
                        response_id=created_response.id,
                        message="Response created successfully"
                    ))

            except Exception as e:
                # Catch any unexpected errors for an individual item
                logger.error(f"Error processing question '{item_payload.question_id}' for attempt '{item_payload.attempt_id}': {str(e)}")
                results.append(SubmitResponseResult(
                    question_id=item_payload.question_id,
                    status="failed",
                    message=f"Processing error: {str(e)}"
                ))
                # Continue processing other items in the batch
                
    except HTTPException:
        # Re-raise HTTP exceptions that were explicitly raised (e.g., USER_NOT_FOUND)
        raise
    except Exception as e:
        # Catch any other top-level unexpected errors
        logger.error(f"Critical error during batch submission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during batch processing."
        )

    # Return the results for the entire batch
    return {"status": "batch_processing_completed", "results": results}
        
@router.post("/attempt/{id}/finish")
async def submit_question_response(id: str, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(
            where={
                "auth0_id": user_id
            }
        )
        if not user:
            raise Exception("USER_NOT_FOUND")
        
        attempt = await prisma.testattempt.find_first(
            where={
                "id": id,
                "user_id": user.auth0_id
            }
        )
        
        if not attempt:
            raise Exception("TEST_ATTEMPT_NOT_FOUND")
        
        if attempt.due_at < datetime.now(timezone.utc):
            raise Exception("TEST_ATTEMPT_EXPIRED")
        
        if attempt.status != "IN_PROGRESS":
            raise Exception("TEST_ATTEMPT_NOT_IN_PROGRESS")

        await prisma.testattempt.update(
            where={
                "id": attempt.id
            },
            data={
                "status": "SUBMITTED",
                "submitted_at": datetime.now(timezone.utc),
                "finish_id": user.auth0_id
            }
        )
        graded_attempt = await grade_test(attempt.id)
        # send openai request
        
        return graded_attempt


    except Exception as e:
        logger.error(f"Error finishing test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
        
        
@router.get("/attempt/{id}/insights")
async def gather_insights(id: str, auth_result: str = Security(auth.verify)):
    # try:
    user_id = auth_result["sub"]
    user = await prisma.user.find_first(
        where={
            "auth0_id": user_id
        }
    )
    if not user:
        raise Exception("USER_NOT_FOUND")
    
    attempt = await prisma.testattempt.find_first(
        where={
            "id": id,
            "user_id": user.auth0_id
        }
    )
    
    if not attempt:
        raise Exception("TEST_ATTEMPT_NOT_FOUND")
    # return attempt
    if attempt.status not in ["GRADED", "SUBMITTED"]:
        raise Exception("TEST_ATTEMPT_NOT_GRADED")
    
    full_payload = await get_clean_feedback_payload(attempt.id)
    grammar_section = next(
        (s for s in full_payload["sections"] if s["section_name"].strip().upper() == "VOCABULARY"),
        None
    )
    if not grammar_section:
        raise Exception("VOCABULARY section not found in test attempt.")

    # Build the assistant input (minimal, structured)
    assistant_input = {
        "mode": "VOCABULARY_FEEDBACK_ONLY",
        "meta": {
            "attempt_id": attempt.id,
            "test_title": full_payload.get("test_title"),
        },
        "grammar": {
            "questions": grammar_section["questions"]
        }
    }
    insights_payload = await gather_insight_data(attempt.id)
    # Let the Assistant create the final formatted feedback
    merged_report = await grade_yesh(json.dumps(assistant_input, ensure_ascii=False))
    return {"type": "markdown", "content": merged_report}

    # except Exception as e:
    #     logger.error(f"Error gathering insights: {str(e)}")
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail=str(e)
    #     )


#Senge
# ─────────────────────────────────────────────────────────
# GET /api/test/list
# GET /api/test/list?page=1
# ─────────────────────────────────────────────────────────
@router.get("/list")
async def list_tests(
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
):
    try:
        skip = (page - 1) * per_page
        total_count = await prisma.test.count()
        raw_tests = await prisma.test.find_many(
            skip=skip,
            take=per_page,
            order={"createdAt": "desc"}
        )
        tests = [
            {
                "id": t.id,
                "title": t.title,
                "subject": t.subject,
                "duration": t.duration,
                "description": t.description,
            }
            for t in raw_tests
        ]
        return {
            "status": "success",
            "tests": tests,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page
            }
        }
    except Exception as e:
        logger.error(f"Error listing tests: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
# ─────────────────────────────────────────────────────────
# 3) GET /api/test/{id}  (full test details for student)
# ─────────────────────────────────────────────────────────
@router.get("/{id}")
async def get_test(id: str):
    test = await prisma.test.find_first(
        where={"id": id},
        include={
            "sections": {
                "include": {
                    "tasks": {
                        "include": {"questions": {"include": {"options": True}}}
                    },
                    "questions": {"include": {"options": True}}
                }
            }
        }
    )
    print("here")
    if not test:
        raise HTTPException(status_code=404, detail="TEST_NOT_FOUND")
    return test


# ─────────────────────────────────────────────────────────
# 4) GET /api/test/attempts
# /api/test/attempts?page=1
# ─────────────────────────────────────────────────────────
@router.get("/user/attempts")
async def list_user_attempts(
    auth_result: str = Security(auth.verify),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
):
    try:
        user_id = auth_result["sub"]
        user = await prisma.user.find_first(where={"auth0_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USER_NOT_FOUND"
            )

        skip = (page - 1) * per_page
        total_attempts = await prisma.testattempt.count(
            where={"user_id": user.auth0_id}
        )

        raw_attempts = await prisma.testattempt.find_many(
            where={"user_id": user.auth0_id},
            order={"started_at": "desc"},
            skip=skip,
            take=per_page,
            include={"test": True}
        )

        attempts = []
        for a in raw_attempts:
            test = a.test
            attempts.append({
                "id": a.id,
                "status": a.status,
                "started_at": a.started_at,
                "submitted_at": a.submitted_at,
                "due_at": a.due_at,
                "score": a.score,
                "test": {
                    "id": test.id,
                    "title": test.title,
                    "subject": test.subject,
                    "duration": test.duration,
                    "description": test.description,
                } if test else None
            })

        return {
            "status": "success",
            "attempts": attempts,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_attempts,
                "total_pages": (total_attempts + per_page - 1) // per_page
            }
        }

    except Exception as e:
        logger.error(f"Error listing user attempts: {e}")
        raise HTTPException(
            status_code=400,
            detail="FAILED_TO_FETCH_TEST_ATTEMPTS"
        )
# ─────────────────────────────────────────────────────────
# 5) GET /api/test/attempt/{id}
# ─────────────────────────────────────────────────────────
@router.get("/attempt/{id}")
async def get_user_attempt(id: str, auth_result: str = Security(auth.verify)):
    try:
        user_id = auth_result["sub"]

        # Fetch the authenticated user
        user = await prisma.user.find_first(where={"auth0_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USER_NOT_FOUND"
            )

        # Fetch the attempt that belongs to the user
        attempt = await prisma.testattempt.find_first(
            where={"id": id, "user_id": user.auth0_id}
        )
        if not attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEST_ATTEMPT_NOT_FOUND"
            )

        # Fetch test details
        test = await prisma.test.find_first(where={"id": attempt.test_id})
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEST_NOT_FOUND"
            )

        # Format test data
        test_data = {
            "id": test.id,
            "title": test.title,
            "subject": test.subject,
            "duration": test.duration,
            "description": test.description,
        }

        # Fetch user responses for this attempt
        responses = await prisma.response.find_many(where={"attempt_id": attempt.id})

        # Format the attempt data
        attempt_data = {
            "id": attempt.id,
            "test": test_data,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "submitted_at": attempt.submitted_at,
            "due_at": attempt.due_at,
            "report": getattr(attempt, "report", None),
            "responses": responses,
        }

        if hasattr(attempt, "score"):
            attempt_data["score"] = attempt.score

        return {
            "status": "success",
            "attempt": attempt_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving attempt detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Something went wrong while fetching the attempt"
        )

