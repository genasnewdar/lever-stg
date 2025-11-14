from app.singleton import prisma
from typing import Dict, Any, List
from datetime import datetime
import json


async def grade_test(attempt_id: str):
    # Fetch the test attempt in the "SUBMITTED" state,
    # including all responses, each with its question and the question's options.
    attempt = await prisma.testattempt.find_first(
        where={
            "id": attempt_id,
            "status": "SUBMITTED"
        },
        include={
            "responses": {
                "include": {
                    "question": {
                        "include": {
                            "options": True  # So we can auto-grade multiple choice questions.
                        }
                    }
                }
            }
        }
    )
    
    if not attempt:
        raise Exception("SUBMITTED_TEST_ATTEMPT_NOT_FOUND")
    
    total_score = 0

    for response in attempt.responses:
        # Retrieve the associated question data.
        question = response.question
        if not question:
            continue  # Skip if the question is missing.
            
        question_type = question.type
        question_points = question.points
        is_correct = None  # Default for questions not auto-graded.
        points_awarded = 0

        # Auto-grade based on question type.
        if question_type == "MULTIPLE_CHOICE":
            # For multiple-choice, retrieve the correct option id.
            options = question.options
            correct_option_id = None
            for option in options:
                if option.is_correct:
                    correct_option_id = option.id
                    break
            # Check if the student's selected option matches the correct option.
            if correct_option_id and response.selected_option == correct_option_id:
                is_correct = True
                points_awarded = question_points
            else:
                is_correct = False

        elif question_type == "MATCHING":
            # For matching questions, compare the provided matching JSON with the correct mapping.
            correct_mapping = question.correctMapping
            matching_items = question.matchingItems
            student_mapping = response.additional_data
            
            grade_matching_result = grade_matching(student_mapping, correct_mapping, matching_items)
            is_correct = grade_matching_result.get("is_correct")
            points_awarded = grade_matching_result.get("points_awarded")

        # For questions that are not auto-graded, we'll leave is_correct as None.

        # Update this response record with the auto-grading result.
        await prisma.response.update(
            where={"id": response.id},
            data={
                "is_correct": is_correct,
                "points_awarded": points_awarded
            }
        )

        # Increment the total score for all correct answers.
        if is_correct:
            total_score += points_awarded

    # After processing all responses, update the test attempt with the total score
    # and mark it as graded.
    graded_attempt = await prisma.testattempt.update(
        where={"id": attempt_id},
        data={
            "score": total_score,
            "status": "GRADED"
        }
    )
    
    max_point = await get_maximum_point(graded_attempt.test_id)

    return {
        "graded": graded_attempt,
        "max_point": max_point,
        "percentage": round((total_score / max_point) * 100, 2) if max_point > 0 else 0
    }



async def get_maximum_point(test_id: str) -> int:
    # Retrieve the test along with sections, section questions, and task questions.
    test = await prisma.test.find_unique(
        where={"id": test_id},
        include={
            "sections": {
                "include": {
                    "questions": True,  # Direct questions under section.
                    "tasks": {
                        "include": {
                            "questions": True  # Questions under each task.
                        }
                    }
                }
            }
        }
    )
    
    if not test:
        raise Exception("Test not found")
    
    max_points = 0

    # Iterate over each section in the test.
    for section in test.sections:
        # Sum points for direct questions in the section.
        for question in section.questions:
            points = question.points
            if points is not None:
                max_points += points

        # Sum points for questions in each task of the section.
        for task in section.tasks:
            for question in task.questions:
                points = question.points
                if points is not None:
                    max_points += points

    return max_points




def grade_matching(student_mapping, correct_mapping, matching_items):
    """
    Compare student mapping with the correct mapping.
    """
    # For matching questions, build the correct mapping from matchingItems and correctMapping.
    # correct_mapping = question.get("correctMapping")
    # matching_items = question.get("matchingItems")
    # student_mapping = response.get("additional_data")
    if correct_mapping is not None and matching_items is not None and student_mapping is not None:
        correct_count = 0
        left_items = matching_items.get("left", [])
        right_items = matching_items.get("right", [])
        total_matches = len(left_items)
        # Iterate through each left item.
        for i, left_item in enumerate(left_items):
            key = f"k{i}"
            if key not in correct_mapping:
                continue
            try:
                right_index = int(correct_mapping[key])
            except Exception:
                continue
            if right_index < len(right_items):
                correct_right = right_items[right_index]
                # Get the student's answer for this left item.
                student_answer = student_mapping.get(left_item)
                if student_answer == correct_right:
                    correct_count += 1
        # Each correct match is worth one point.
        points_awarded = correct_count
        # Mark the question as fully correct only if all matches are correct.
        is_correct = (correct_count == total_matches)
    else:
        is_correct = False
        points_awarded = 0
        
        
    return {
        "is_correct": is_correct,
        "points_awarded": points_awarded
    }
    
# Example usage of the grade_matching function
# grade_matching(
# {
#     "to provoke": "Finally, her behavior began to <u>irritate</u> him.",
#     "significant": "",
#     "to pacify": "",
#     "to decrease": "",
#     "to persuade": "He managed to <u>convince</u> the jury of his innocence.",
#     "to imitate": "",
#     "rapid": "",
#     "constant": ""
# },
# {
#     "k0": "1",
#     "k1": "6",
#     "k2": "5",
#     "k3": "2",
#     "k4": "0",
#     "k5": "3",
#     "k6": "7",
#     "k7": "4"
# },
# {
#     "left": [
#         "to provoke",
#         "significant",
#         "to pacify",
#         "to decrease",
#         "to persuade",
#         "to imitate",
#         "rapid",
#         "constant"
#     ],
#     "right": [
#         "He managed to <u>convince</u> the jury of his innocence.",
#         "Finally, her behavior began to <u>irritate</u> him.",
#         "The number of workers has <u>declined</u> during Covid-19 pandemic.",
#         "She <u>resembles</u> her other very closely.",
#         "My computer makes a <u>continuous</u> low buzzing noise.",
#         "Mom would take me in her arms and <u>soothe</u> me.",
#         "Mining is the most <u>important</u> sector in our economics.",
#         "He thinks, he is a reasonably <u>quick</u> learner."
#     ]
# }
# )




async def gather_insight_data_v2(attempt_id: str) -> Dict[str, Any]:
    """
    Gathers comprehensive data about a student's test attempt, including:
      - Student and test info
      - Final and maximum score
      - Time taken (based on started_at vs. submitted_at)
      - Section-level summaries
      - Full per-question details:
          * text, type, points
          * correct answers (via is_correct for options, or numeric/formula/matching data)
          * student's response (points_awarded, is_correct, numeric_answer, selected_option, additional_data)
    """
    # 1. Fetch the attempt along with all the details needed for a thorough analysis.
    #    We include:
    #      - user (for student name)
    #      - test (for title, etc.)
    #      - responses -> question -> [options, section, task]
    attempt = await prisma.testattempt.find_unique(
        where={"id": attempt_id},
        include={
            "user": True,
            "test": True,
            "responses": {
                "include": {
                    "question": {
                        "include": {
                            "options": True,
                            # "section": True,
                            "task": {
                                "include": {
                                    "section": True
                                }
                            }
                        }
                    }
                }
            }
        }
    )
    if not attempt:
        raise ValueError("Test attempt not found.")

    # 2. Basic info
    if attempt.status not in ["GRADED", "SUBMITTED"]:
        # If you only want fully submitted or graded attempts, raise an error
        # or handle differently as needed.
        raise ValueError(f"Test attempt is not yet GRADED: {attempt.status}")

    student_name = attempt.user.full_name
    test_title = attempt.test.title
    score = attempt.score or 0.0
    status = attempt.status

    # Time taken: difference between submitted_at and started_at (optional).
    started_at = attempt.started_at
    submitted_at = attempt.submitted_at
    time_taken_minutes = None
    if submitted_at and started_at:
        # Convert to Python datetime objects if they aren't already
        start_dt = started_at if isinstance(started_at, datetime) else datetime.fromisoformat(started_at)
        submit_dt = submitted_at if isinstance(submitted_at, datetime) else datetime.fromisoformat(submitted_at)
        diff = submit_dt - start_dt
        time_taken_minutes = round(diff.total_seconds() / 60.0, 2)

    # 3. Compute the maximum score for the entire test.
    test_id = attempt.test.id
    max_score = await get_maximum_point(test_id)

    # 4. Summarize each section's performance and build a breakdown for all questions.
    #    We store partial results in a map: section_id -> {name, total_score, questions: []}
    section_map = {}

    # For each response, gather question + response details.
    # Some questions belong to a Section, others to a Task, or both might be None,
    # so we handle whichever is present.
    for resp in attempt.responses:
        question = resp.question
        if not question:
            continue

        # Identify which section to place this question under, if any.
        # If a question is in a task, it might also have a parent section. We'll prefer
        # question.section if it exists, else we can fallback to question.task?
        # By your schema, a question can belong to either section or task, or both if you allow it.
        section = question.task.section
        section_id = section.id if section else None
        section_name = section.name if section else "UNKNOWN_SECTION"

        # Initialize the section entry if we haven't encountered it yet.
        if section_id and section_id not in section_map:
            section_map[section_id] = {
                "section_name": section_name,
                "section_score": 0.0,
                "questions": []
            }

        # Build a correct answers list or object. This depends on question type.
        correct_answers = {}
        q_type = question.type

        # For multiple choice, find the option(s) with is_correct = True
        if q_type == "MULTIPLE_CHOICE":
            # Gather the correct option IDs
            correct_options = [opt.text for opt in question.options if opt.is_correct]
            correct_answers["multiple_choice"] = correct_options

        # # For numeric answers
        # if q_type == "NUMERIC_ANSWER" and question.get("correctNumericAnswer") is not None:
        #     correct_answers["numeric_answer"] = question["correctNumericAnswer"]

        # For matching
        if q_type == "MATCHING":
            correct_answers["matching"] = {
                "matchingItems": question.matchingItems,  # left/right pairs
                "correctMapping": question.correctMapping # e.g. { "k0": "1", ... }
            }

        # # If there's a correct formula
        # if question.get("correctFormulaLatex"):
        #     correct_answers["formula"] = question["correctFormulaLatex"]

        # Build the question details
        question_data = {
            "question_id": question.id,
            "question_text": question.text,
            "question_type": question.type,
            "question_points": question.points,
            "correct_answers": correct_answers,
            "student_response": {
                "response_id": resp.id,
                "selected_option": resp.selected_option,
                "numeric_answer": resp.numeric_answer,
                "additional_data": resp.additional_data,
                "points_awarded": resp.points_awarded,
                "is_correct": resp.is_correct,
            },
        }

        # Accumulate the points awarded into the section's total.
        points_awarded = resp.points_awarded or 0.0
        if section_id:
            section_map[section_id]["section_score"] += points_awarded
            section_map[section_id]["questions"].append(question_data)
        else:
            # If there's truly no section, you could store them under a special key
            # or skip them. Example:
            if "NO_SECTION" not in section_map:
                section_map["NO_SECTION"] = {
                    "section_name": "No Section Found",
                    "section_score": 0.0,
                    "questions": []
                }
            section_map["NO_SECTION"]["section_score"] += points_awarded
            section_map["NO_SECTION"]["questions"].append(question_data)

    # Convert the section_map to a list for easier consumption.
    sections_list = []
    for sec_id, sec_data in section_map.items():
        sections_list.append({
            "section_name": sec_data["section_name"],
            "section_score": sec_data["section_score"],
            "questions": sec_data["questions"]
        })

    # 5. Return an object with all the data your AI prompt might need.
    #    Expand further with skill‐level analysis or previously attempted tests if desired.
    return {
        "student_name": student_name,
        "test_title": test_title,
        "score": score,
        "maximum_score": max_score,
        "status": status,
        "time_taken_minutes": time_taken_minutes,
        "sections": sections_list
    }
    
    
async def get_clean_feedback_payload(attempt_id: str) -> Dict[str, Any]:
    """
    Gathers a clean, compressed payload for AI feedback generation.
    Each question is represented as an array:
    [question_type, question_text, points, options, correct_answer, student_answer]
    For MATCHING type, correct_answer and student_answer are JSON strings.
    """
    attempt = await prisma.testattempt.find_unique(
        where={"id": attempt_id},
        include={"user": True, "test": True}
    )
    if not attempt:
        raise ValueError("Attempt not found")

    full_test = await prisma.test.find_unique(
        where={"id": attempt.test.id},
        include={
            "sections": {
                "include": {
                    "questions": {"include": {"options": True}},
                    "tasks": {
                        "include": {
                            "questions": {"include": {"options": True}}
                        }
                    }
                }
            }
        }
    )
    if not full_test:
        raise ValueError("Test structure not found")

    responses = await prisma.response.find_many(
        where={"attempt_id": attempt_id},
        include={"question": True}
    )
    response_map = {r.question.id: r for r in responses if r.question}

    def simplify_question(q):
        q_type = q.type
        correct = None
        if q_type == "MULTIPLE_CHOICE":
            correct_raw = [opt.text for opt in q.options if opt.is_correct]
            correct = correct_raw[0] if len(correct_raw) == 1 else correct_raw
        elif q_type == "NUMERIC_ANSWER":
            correct = q.correctNumericAnswer
        elif q_type == "MATCHING":
            correct = json.dumps({"items": q.matchingItems, "mapping": q.correctMapping})
        elif q.correctFormulaLatex:
            correct = q.correctFormulaLatex

        response = response_map.get(q.id)
        student_answer = None
        if response:
            if q_type == "MULTIPLE_CHOICE":
                selected_opt = next((opt.text for opt in q.options if opt.id == response.selected_option), None)
                student_answer = selected_opt
            elif q_type == "NUMERIC_ANSWER":
                student_answer = response.numeric_answer
            elif q_type == "MATCHING":
                student_answer = json.dumps(response.additional_data)
            elif q_type in ["SHORT_ANSWER", "ESSAY"]:
                student_answer = response.answer_text

        # Return as array: [type, text, points, options, correct, student]
        return [
            q_type,
            q.text,
            q.points,
            [opt.text for opt in q.options],
            correct,
            student_answer
        ]

    section_data = []
    for section in full_test.sections:
        questions = []

        for q in section.questions:
            questions.append(simplify_question(q))

        for task in section.tasks:
            for tq in task.questions:
                questions.append(simplify_question(tq))

        section_data.append({
            "section_name": section.name,
            "questions": questions
        })

    # Final payload
    return {
        "student_name": attempt.user.full_name,
        "test_title": attempt.test.title,
        "score": attempt.score,
        "maximum_score": await get_maximum_point(attempt.test.id),
        "time_taken_minutes": (
            round((attempt.submitted_at - attempt.started_at).total_seconds() / 60.0, 2)
            if attempt.started_at and attempt.submitted_at else None
        ),
        "sections": section_data
    }

async def gather_insight_data(attempt_id: str) -> Dict[str, Any]:
    """
    Gathers comprehensive data about a student's GRADED test attempt, including:
      - Student and test info
      - Final and maximum score
      - Time taken (based on started_at vs. submitted_at)
      - Section-level summaries
      - Full per-question details (including unanswered questions)
    """
    # 1. Fetch the test attempt. Confirm it's GRADED.
    attempt = await prisma.testattempt.find_unique(
        where={"id": attempt_id},
        include={
            "user": True,
            "test": True
        }
    )
    if not attempt:
        raise ValueError("Test attempt not found.")
    
    if attempt.status not in ["GRADED", "SUBMITTED"]:
        raise ValueError(f"Test attempt must be GRADED, but got {attempt.status}")

    # 2. Basic info
    student_name = attempt.user.full_name
    test_title = attempt.test.title
    score = attempt.score or 0.0
    status = attempt.status

    # 3. Time taken calculation
    time_taken_minutes = None
    if attempt.submitted_at and attempt.started_at:
        start_dt = attempt.started_at if isinstance(attempt.started_at, datetime) else datetime.fromisoformat(attempt.started_at)
        submit_dt = attempt.submitted_at if isinstance(attempt.submitted_at, datetime) else datetime.fromisoformat(attempt.submitted_at)
        diff = submit_dt - start_dt
        time_taken_minutes = round(diff.total_seconds() / 60.0, 2)

    # 4. Fetch the full test with all sections, tasks, and their questions.
    test_id = attempt.test.id
    full_test = await prisma.test.find_unique(
        where={"id": test_id},
        include={
            "sections": {
                "include": {
                    "questions": {
                        "include": {
                            "options": True
                        }
                    },
                    "tasks": {
                        "include": {
                            "questions": {
                                "include": {
                                    "options": True
                                }
                            }
                        }
                    }
                }
            }
        }
    )
    if not full_test:
        raise ValueError("Associated test not found or has been removed.")

    # 5. Gather all the student's responses.
    responses = await prisma.response.find_many(
        where={"attempt_id": attempt_id},
        include={"question": True}
    )
    response_map = {}  # Map question_id -> response object
    for r in responses:
        # Using dot notation for fields.
        if r.question:
            response_map[r.question.id] = r

    # 6. Compute the maximum score
    max_score = await get_maximum_point(test_id)

    # 7. Build a section-wise breakdown, including unanswered questions.
    section_map = {}  # section_id -> { section_name, section_score, questions: [] }

    # Helper: process each question and store in our structure.
    def process_question(question_obj, section_id: str, section_name: str) -> None:
        q_type = question_obj.type
        correct_answers = {}

        # For multiple-choice questions
        if q_type == "MULTIPLE_CHOICE":
            correct_options = [opt.text for opt in question_obj.options if opt.is_correct]
            correct_answers["multiple_choice"] = correct_options

        # For numeric answers
        if q_type == "NUMERIC_ANSWER" and question_obj.correctNumericAnswer is not None:
            correct_answers["numeric_answer"] = question_obj.correctNumericAnswer

        # For matching questions
        if q_type == "MATCHING":
            correct_answers["matching"] = {
                "matchingItems": question_obj.matchingItems,
                "correctMapping": question_obj.correctMapping
            }

        # For formula-based questions
        if question_obj.correctFormulaLatex:
            correct_answers["formula"] = question_obj.correctFormulaLatex

        # Check if there's a response for this question.
        resp = response_map.get(question_obj.id)
        if resp:
            student_response = {
                "response_id": resp.id,
                "selected_option": resp.selected_option,
                "numeric_answer": resp.numeric_answer,
                "additional_data": resp.additional_data,
                "points_awarded": resp.points_awarded,
                "is_correct": resp.is_correct
            }
            points_awarded = resp.points_awarded or 0.0
        else:
            # Not answered – use placeholder values.
            student_response = {
                "response_id": None,
                "selected_option": None,
                "numeric_answer": None,
                "additional_data": None,
                "points_awarded": 0,
                "is_correct": False
            }
            points_awarded = 0.0

        question_data = {
            "question_id": question_obj.id,
            "question_text": question_obj.text,
            "question_type": q_type,
            "question_points": question_obj.points,
            "correct_answers": correct_answers,
            "student_response": student_response
        }

        # Insert question into section_map.
        if section_id not in section_map:
            section_map[section_id] = {
                "section_name": section_name,
                "section_score": 0.0,
                "questions": []
            }
        section_map[section_id]["section_score"] += points_awarded
        section_map[section_id]["questions"].append(question_data)

    # 8. Process each section's questions and task questions.
    for sec in full_test.sections:
        sec_id = sec.id
        sec_name = sec.name

        # Process direct questions under the section.
        for q_obj in sec.questions:
            process_question(q_obj, sec_id, sec_name)

        # Process questions under tasks in this section.
        for task_obj in sec.tasks:
            for t_q in task_obj.questions:
                # If question doesn't have its own section, assign it to the parent section.
                process_question(t_q, sec_id, sec_name)

    # 9. Convert section_map to a list.
    sections_list = []
    for sec_data in section_map.values():
        sections_list.append({
            "section_name": sec_data["section_name"],
            "section_score": sec_data["section_score"],
            "questions": sec_data["questions"]
        })

    # 10. Return all data to be used in the AI prompt.
    return {
        "student_name": student_name,
        "test_title": test_title,
        "score": score,
        "maximum_score": max_score,
        "status": status,
        "time_taken_minutes": time_taken_minutes,
        "sections": sections_list
    }