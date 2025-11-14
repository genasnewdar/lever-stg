import time
import json
import logging
from fastapi import APIRouter, HTTPException, Security, status
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from app.auth.auth import VerifyToken
from app.singleton import prisma

router = APIRouter(prefix="/api/admin/test")
auth = VerifyToken()
start_time = time.time()

# Set up logging (configure handlers/levels as needed)
logger = logging.getLogger("admin_test")
logger.setLevel(logging.INFO)

# ----------------------------
# Pydantic Models for Payload
# ----------------------------
class OptionCreate(BaseModel):
    label: str
    text: str
    order: int
    is_correct: Optional[bool] = False

class QuestionCreate(BaseModel):
    questionNumber: Optional[str] = None  # e.g., "2.1(a)"
    text: str                           # Full question text; ensure markup is clean
    points: int                         # Points allocated for the question
    type: str                           # Must be one of the QuestionType enum values
    options: Optional[List[OptionCreate]] = []  # For multiple-choice, matching, etc.
    correctOptionId: Optional[str] = None
    correctNumericAnswer: Optional[float] = None
    correctFormulaLatex: Optional[str] = None
    # For matching questions, we now expect a JSON string (to be parsed)
    matchingItems: Optional[dict] = None   # E.g., '{"left": [...], "right": [...]}' 
    correctMapping: Optional[dict] = None    # E.g., '{"0": "2", "1": "0", ...}'

class TaskCreate(BaseModel):
    title: Optional[str] = None         # e.g., "Task 1: Reading Passage"
    instructions: Optional[str] = None    # Task-level instructions
    passage: Optional[str] = None         # A large passage (if needed)
    order: int
    questions: List[QuestionCreate] = []

class SectionCreate(BaseModel):
    name: str                           # e.g., "GRAMMAR", "READING", etc.
    instructions: Optional[str] = None
    order: int
    tasks: Optional[List[TaskCreate]] = []        # Optional tasks within this section.
    questions: Optional[List[QuestionCreate]] = []  # Direct questions (if no tasks)

class AdminCreateTestRequest(BaseModel):
    subject: str                        # e.g., "MATH" or "ENGLISH"
    duration: int
    title: str
    description: Optional[str] = None
    instructions: Optional[str] = None
    sections: List[SectionCreate]

# ------------------------------------------
# Helper function to wrap nested create fields for Prisma
# ------------------------------------------
def wrap_create_field(data: dict, field: str):
    """
    If the given field exists in data and is a list,
    wrap it in a dict with a "create" key for Prisma nested writes.
    """
    if field in data and isinstance(data[field], list):
        data[field] = {"create": data[field]}

def adjust_correct_mapping(mapping: Dict[Any, Any]) -> Dict[str, Any]:
    """
    Adjust keys in a mapping so that they start with a letter.
    For example, converts {"0": "2", "1": "0"} into {"k0": "2", "k1": "0"}.
    """
    new_mapping = {}
    for key, value in mapping.items():
        new_key = f"k{str(key)}"
        new_mapping[new_key] = str(value)
        
    print(f"Adjusted mapping: {new_mapping}")
    return new_mapping

def process_question(question: dict):
    """
    Process a single question dictionary to:
    - Wrap "options" array with "create"
    - Parse matchingItems and correctMapping fields from JSON strings if provided.
    """
    wrap_create_field(question, "options")
    if "matchingItems" in question and isinstance(question["matchingItems"], dict):
        try:
            question["matchingItems"] = json.dumps(question["matchingItems"])
        except Exception as e:
            logger.error("Error parsing matchingItems: %s", e)
            raise HTTPException(status_code=400, detail="Invalid JSON in matchingItems")
    if "correctMapping" in question and isinstance(question["correctMapping"], dict):
        try:            
            question["correctMapping"] = adjust_correct_mapping(question["correctMapping"])
            question["correctMapping"] = json.dumps(question["correctMapping"])
        except Exception as e:
            logger.error("Error parsing correctMapping: %s", e)
            raise HTTPException(status_code=400, detail="Invalid JSON in correctMapping")
    return question

# ----------------------------
# Admin Create Test Endpoint
# ----------------------------
@router.post("")
async def create_test(payload: AdminCreateTestRequest):
    # Convert payload into a dict (excluding None values)
    test_data = payload.model_dump(exclude_none=True)

    if "sections" in test_data:
        sections_list = test_data["sections"]
        for section in sections_list:
            wrap_create_field(section, "tasks")
            wrap_create_field(section, "questions")
            if "tasks" in section:
                for task in section["tasks"]["create"]:
                    wrap_create_field(task, "questions")
                    if "questions" in task:
                        for idx, question in enumerate(task["questions"]["create"]):
                            task["questions"]["create"][idx] = process_question(question)
            if "questions" in section:
                for idx, question in enumerate(section["questions"]["create"]):
                    section["questions"]["create"][idx] = process_question(question)
        test_data["sections"] = {"create": sections_list}

    try:
        created_test = await prisma.test.create(data=test_data)
        return created_test
    except Exception as e:
        logger.error("Error creating test: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    

def remove_sensitive_fields(test_data: dict) -> dict:
    """
    Recursively remove sensitive keys from questions and options in the test_data.
    Removes:
      - From each question: "correctNumericAnswer", "correctFormulaLatex", "correctMapping"
      - From each option: "is_correct"
    """
    sensitive_question_keys = ["correctNumericAnswer", "correctFormulaLatex", "correctMapping"]

    # Process a list of questions.
    def process_questions(questions: list):
        for question in questions:
            # Remove sensitive question keys if they exist.
            for key in sensitive_question_keys:
                question.pop(key, None)
            # If the question has options, remove sensitive keys from them.
            if "options" in question and isinstance(question["options"], list):
                for option in question["options"]:
                    option.pop("is_correct", None)

    # Process sections.
    sections = test_data.get("sections", [])
    for section in sections:
        # Process questions directly attached to the section.
        if "questions" in section and isinstance(section["questions"], list):
            process_questions(section["questions"])
        # Process tasks within the section, if any.
        if "tasks" in section and isinstance(section["tasks"], list):
            for task in section["tasks"]:
                if "questions" in task and isinstance(task["questions"], list):
                    process_questions(task["questions"])
    return test_data

@router.get("/{id}")
async def get_test(id: str):
    try:
        test = await prisma.test.find_first(
            where={
                "id": id
            },
            include={
                "sections": {
                    "include": {
                        "tasks": {
                            "include": {
                                "questions": {
                                    "include": {
                                        "options": True
                                    }
                                }
                            }
                        },
                        "questions": {
                            "include": {
                                "options": True
                            }
                        }
                    }
                }
            }
        )
        
        if not test:
            raise HTTPException(status_code=404, detail="TEST_NOT_FOUND")
        
        # test_without_sensitive_fields = remove_sensitive_fields(test.model_dump())
        return test
        
    except Exception as e:
        logger.error("Error creating test: %s", e)
        raise HTTPException(status_code=400, detail=str(e))