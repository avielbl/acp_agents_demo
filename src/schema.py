import operator
from typing import Annotated, List, Optional, TypedDict

from pydantic import BaseModel


class ActionItem(BaseModel):
    description: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    segment_id: int


class BusState(TypedDict):
    goal: str
    done: bool
    mailbox: Annotated[List[dict], operator.add]
    active_role: str
    step: int
    segments: List[str]
    action_items: List[dict]
    validation_issues: List[str]
    retry_count: int


def create_initial_state(transcript: str) -> BusState:
    """Creates the starting BusState for a new pipeline run."""
    return {
        "goal": transcript,
        "done": False,
        "mailbox": [],
        "active_role": "planner",
        "step": 0,
        "segments": [],
        "action_items": [],
        "validation_issues": [],
        "retry_count": 0,
    }
