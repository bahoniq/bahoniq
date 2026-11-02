from dataclasses import dataclass
from enum import Enum


class TaskStatus(str, Enum):
    CREATED = "created"
    ANALYZING = "analyzing"
    NEEDS_INPUT = "needs_input"
    PLANNED = "planned"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    RECOVERY = "recovery"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TRANSITIONS = {
    TaskStatus.CREATED: {TaskStatus.ANALYZING, TaskStatus.CANCELLED},
    TaskStatus.ANALYZING: {
        TaskStatus.NEEDS_INPUT, TaskStatus.PLANNED,
        TaskStatus.FAILED, TaskStatus.CANCELLED,
    },
    TaskStatus.NEEDS_INPUT: {
        TaskStatus.ANALYZING, TaskStatus.PLANNED, TaskStatus.CANCELLED,
    },
    TaskStatus.PLANNED: {
        TaskStatus.QUEUED, TaskStatus.NEEDS_INPUT, TaskStatus.CANCELLED,
    },
    TaskStatus.QUEUED: {
    TaskStatus.RUNNING,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
},
    TaskStatus.RUNNING: {
        TaskStatus.VERIFYING, TaskStatus.RECOVERY,
        TaskStatus.FAILED, TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED, TaskStatus.RECOVERY, TaskStatus.FAILED,
    },
    TaskStatus.RECOVERY: {
        TaskStatus.QUEUED, TaskStatus.FAILED, TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: {TaskStatus.RECOVERY},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


@dataclass(frozen=True)
class Task:
    id: str
    instruction: str
    source_path: str | None
    output_dir: str | None
    status: TaskStatus
    created_at: str
    updated_at: str
    error: str | None = None
    recovery_attempts: int = 0
