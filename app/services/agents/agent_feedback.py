from typing import Tuple, Dict, Any
from .registry import get_worker
from .contracts import SectionSlice

RUBRICS = {
    "GRAMMAR": ["Articles","Tense consistency","Prepositions","Comparatives","Conditionals","Reported speech"],
    "VOCABULARY": ["Collocations","Word forms","Phrasal verbs","Idioms","Topic lexis"],
    "COMMUNICATION": ["Politeness","Functional language","Register","Requests/Offers"],
    "READING": ["Detail","Inference","Paraphrase equivalence","Vocabulary-in-context"],
    "PART 2": ["Word formation","Synonym match","Context clues"],
}

def route(slice: SectionSlice) -> Tuple[str, Dict[str, Any]]:
    key = "objective"  # single reusable worker for all objective sections
    cfg = get_worker(key).copy()
    cfg["rubric"] = RUBRICS.get(slice.section_name, [])
    return key, cfg
