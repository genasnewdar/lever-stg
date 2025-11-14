from typing import Dict, Any, Callable
from .contracts import SectionSlice, SectionInsights

Worker = Callable[[SectionSlice, dict], SectionInsights]

_REGISTRY: Dict[str, Dict[str, Any]] = {}

def register_worker(key: str, fn: Worker, **defaults):
    _REGISTRY[key] = {"fn": fn, **defaults}

def get_worker(key: str):
    return _REGISTRY[key]
