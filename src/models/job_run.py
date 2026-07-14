from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.job import Job


class JobRunStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


class JobRun(BaseModel):
    job_run_id: UUID = Field(default_factory=uuid4)
    job: Job
    status: JobRunStatus = JobRunStatus.PENDING
    captured_output: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exception: str | None = None


class JobException(BaseModel):
    job_exception_id: UUID = Field(default_factory=uuid4)
    job_run_id: UUID
    exception: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
