import operator
from enum import Enum
from typing import Any, Annotated, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class Role(str, Enum):
    planner = "planner"
    executor = "executor"
    validator = "validator"
    user = "user"


class MsgType(str, Enum):
    task = "task"
    result = "result"
    validation_pass = "validation_pass"
    validation_fail = "validation_fail"


class ACPMessage(BaseModel):
    msg_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sender: Role
    receiver: Role
    msg_type: MsgType
    content: str
    meta: Dict[str, Any] = Field(default_factory=dict)
    trace: Dict[str, Any] = Field(default_factory=dict)


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
