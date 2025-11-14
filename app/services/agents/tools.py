from typing import List, Optional, Tuple
from .contracts import QuestionInsight

def safe_get(arr, idx, default=None):
    try:
        return arr[idx]
    except Exception:
        return default

def normalize_prompt(raw: str) -> str:
    return (
        (raw or "")
        .replace("<u>", "_").replace("</u>", "_")
        .replace("<b>", "**").replace("</b>", "**")
        .replace("\n", " ")
        .strip()
    )

def mn_bool(correct: Optional[bool]) -> str:
    if correct is True: return "Зөв"
    if correct is False: return "Буруу"
    return "Мэдээлэл дутуу"

def compute_accuracy(qs: List[QuestionInsight]) -> Tuple[int, int, float]:
    total = len(qs)
    correct = sum(1 for q in qs if q.is_correct is True)
    acc = round(correct / total, 4) if total else 0.0
    return total, correct, acc
def md_answer(val) -> str:
    """Pretty-print student/gold answers in MD."""
    if val is None:
        return "Мэдээлэл дутуу"
    s = str(val)
    # escape triple underscores so they display as blanks
    s = s.replace("___", r"\_\_\_")
    return s