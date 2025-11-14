import logging
from fastapi import APIRouter, HTTPException, status, Request
from app.singleton import prisma
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/api/system/ielts")

# Set up logging
logger = logging.getLogger("ielts_system")
logger.setLevel(logging.INFO)

# ----------------------------
# System Auto-Finish IELTS Test
# ----------------------------
@router.post("/finish")
async def system_finish_ielts_test(request: Request):
    """
    System endpoint to automatically finish IELTS tests when time expires.
    Called by Cloud Tasks scheduler.
    """
    try:
        logger.info("====================== SYSTEM FINISH IELTS TEST ======================")
        
        # Get request body
        body = await request.json()
        logger.info(f"Finish request body: {body}")
        
        attempt_id = body.get("attempt_id")
        if not attempt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing attempt_id in request body"
            )
        
        # Find the test attempt
        test_attempt = await prisma.ieltstestattempt.find_first(
            where={"id": attempt_id},
            include={
                "test": True,
                "user": True
            }
        )
        
        if not test_attempt:
            logger.warning(f"IELTS test attempt not found: {attempt_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test attempt not found"
            )
        
        # Check if test is already finished
        if test_attempt.status in ["FULLY_COMPLETED", "GRADED", "CANCELLED", "EXPIRED"]:
            logger.info(f"IELTS test attempt {attempt_id} already finished with status: {test_attempt.status}")
            return {"status": "already_finished", "current_status": test_attempt.status}
        
        # Determine final status based on current progress
        final_status = "EXPIRED"  # Default to expired for auto-finish
        
        # If user has completed some modules, mark as partially completed
        if test_attempt.status in ["LISTENING_COMPLETED", "READING_COMPLETED", "WRITING_COMPLETED"]:
            final_status = "FULLY_COMPLETED"
        elif test_attempt.status == "IN_PROGRESS":
            final_status = "EXPIRED"
        
        # Update the test attempt
        updated_attempt = await prisma.ieltstestattempt.update(
            where={"id": attempt_id},
            data={
                "status": final_status,
                "submitted_at": datetime.now(timezone.utc)
            }
        )
        
        logger.info(f"IELTS test attempt {attempt_id} finished with status: {final_status}")
        
        # TODO: Trigger grading process if needed
        # await trigger_ielts_grading(attempt_id)
        
        return {
            "status": "success", 
            "message": "IELTS test finished successfully",
            "attempt_id": attempt_id,
            "final_status": final_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finishing IELTS test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error finishing IELTS test: {str(e)}"
        )

# ----------------------------
# System Grade IELTS Test
# ----------------------------
@router.post("/grade")
async def system_grade_ielts_test(request: Request):
    """
    System endpoint to automatically grade IELTS tests.
    This can be called after test completion or as a separate process.
    """
    try:
        body = await request.json()
        attempt_id = body.get("attempt_id")
        
        if not attempt_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing attempt_id in request body"
            )
        
        # Find the test attempt with all responses
        test_attempt = await prisma.ieltstestattempt.find_first(
            where={"id": attempt_id},
            include={
                "test": {
                    "include": {
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
                        }
                    }
                },
                "listening_responses": {
                    "include": {"question": True}
                },
                "reading_responses": {
                    "include": {"question": True}
                }
            }
        )
        
        if not test_attempt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test attempt not found"
            )
        
        # Grade listening section
        listening_score = 0
        listening_total = 0
        
        if test_attempt.test.listening_test:
            listening_score, listening_total = await grade_listening_responses(
                test_attempt.listening_responses,
                test_attempt.test.listening_test
            )
        
        # Grade reading section  
        reading_score = 0
        reading_total = 0
        
        if test_attempt.test.reading_test:
            reading_score, reading_total = await grade_reading_responses(
                test_attempt.reading_responses,
                test_attempt.test.reading_test
            )
        
        # Convert raw scores to band scores
        listening_band = convert_to_band_score("LISTENING", listening_score)
        reading_band = convert_to_band_score("READING", reading_score)
        
        # Writing and Speaking would need human grading or AI grading
        # For now, set them as None or default values
        writing_band = None  # Requires manual grading
        speaking_band = None  # Requires manual grading
        
        # Calculate overall band (average of all modules)
        band_scores = [band for band in [listening_band, reading_band, writing_band, speaking_band] if band is not None]
        overall_band = sum(band_scores) / len(band_scores) if band_scores else None
        
        # Update the test attempt with scores
        updated_attempt = await prisma.ieltstestattempt.update(
            where={"id": attempt_id},
            data={
                "listening_score": listening_score,
                "reading_score": reading_score,
                "listening_band": listening_band,
                "reading_band": reading_band,
                "writing_band": writing_band,
                "speaking_band": speaking_band,
                "overall_band": overall_band,
                "status": "GRADED" if writing_band and speaking_band else "PARTIALLY_GRADED"
            }
        )
        
        logger.info(f"IELTS test {attempt_id} graded: L:{listening_band}, R:{reading_band}, Overall:{overall_band}")
        
        return {
            "status": "success",
            "attempt_id": attempt_id,
            "scores": {
                "listening": {"raw": listening_score, "band": listening_band},
                "reading": {"raw": reading_score, "band": reading_band},
                "writing": {"band": writing_band},
                "speaking": {"band": speaking_band},
                "overall": overall_band
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error grading IELTS test: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error grading IELTS test: {str(e)}"
        )

# ----------------------------
# Helper Functions
# ----------------------------
async def grade_listening_responses(responses, listening_test):
    """Grade listening responses and return raw score and total possible"""
    correct_answers = 0
    total_questions = 0
    
    # Build a lookup of correct answers
    correct_answers_lookup = {}
    for section in listening_test.sections:
        for question in section.questions:
            total_questions += 1
            correct_answers_lookup[question.id] = {
                "correct_answer": question.correct_answer,
                "options": {opt.id: opt.is_correct for opt in question.options}
            }
    
    # Grade each response
    for response in responses:
        question_id = response.question_id
        user_answer = response.answer.strip().lower() if response.answer else ""
        
        if question_id in correct_answers_lookup:
            correct_data = correct_answers_lookup[question_id]
            
            # Check if it's a direct answer match
            if correct_data["correct_answer"]:
                correct_answer = correct_data["correct_answer"].strip().lower()
                if user_answer == correct_answer:
                    correct_answers += 1
                    # Update response as correct
                    await prisma.ieltslisteningresponse.update(
                        where={"id": response.id},
                        data={"is_correct": True}
                    )
            
            # Or check if it's a multiple choice option
            elif correct_data["options"]:
                # Assuming user_answer is the option ID or label
                for opt_id, is_correct in correct_data["options"].items():
                    if is_correct and (user_answer == opt_id or user_answer in opt_id.lower()):
                        correct_answers += 1
                        await prisma.ieltslisteningresponse.update(
                            where={"id": response.id},
                            data={"is_correct": True}
                        )
                        break
    
    return correct_answers, total_questions

async def grade_reading_responses(responses, reading_test):
    """Grade reading responses and return raw score and total possible"""
    correct_answers = 0
    total_questions = 0
    
    # Build a lookup of correct answers
    correct_answers_lookup = {}
    for passage in reading_test.passages:
        for question in passage.questions:
            total_questions += 1
            correct_answers_lookup[question.id] = {
                "correct_answer": question.correct_answer,
                "options": {opt.id: opt.is_correct for opt in question.options}
            }
    
    # Grade each response (similar logic to listening)
    for response in responses:
        question_id = response.question_id
        user_answer = response.answer.strip().lower() if response.answer else ""
        
        if question_id in correct_answers_lookup:
            correct_data = correct_answers_lookup[question_id]
            
            if correct_data["correct_answer"]:
                correct_answer = correct_data["correct_answer"].strip().lower()
                if user_answer == correct_answer:
                    correct_answers += 1
                    await prisma.ieltsreadingresponse.update(
                        where={"id": response.id},
                        data={"is_correct": True}
                    )
            
            elif correct_data["options"]:
                for opt_id, is_correct in correct_data["options"].items():
                    if is_correct and (user_answer == opt_id or user_answer in opt_id.lower()):
                        correct_answers += 1
                        await prisma.ieltsreadingresponse.update(
                            where={"id": response.id},
                            data={"is_correct": True}
                        )
                        break
    
    return correct_answers, total_questions

def convert_to_band_score(module: str, raw_score: int) -> Optional[float]:
    """Convert raw score to IELTS band score"""
    # This is a simplified conversion - you should implement the actual IELTS scoring
    # or use the IeltsBandConversion table from your schema
    
    band_conversions = {
        "LISTENING": {
            39: 9.0, 37: 8.5, 35: 8.0, 32: 7.5, 30: 7.0,
            26: 6.5, 23: 6.0, 18: 5.5, 16: 5.0, 13: 4.5,
            10: 4.0, 8: 3.5, 6: 3.0, 4: 2.5, 3: 2.0
        },
        "READING": {
            39: 9.0, 37: 8.5, 35: 8.0, 33: 7.5, 30: 7.0,
            27: 6.5, 23: 6.0, 19: 5.5, 15: 5.0, 13: 4.5,
            10: 4.0, 8: 3.5, 6: 3.0, 4: 2.5, 3: 2.0
        }
    }
    
    if module not in band_conversions:
        return None
    
    conversion_table = band_conversions[module]
    
    # Find the closest raw score
    for score in sorted(conversion_table.keys(), reverse=True):
        if raw_score >= score:
            return conversion_table[score]
    
    return 1.0  # Minimum band score