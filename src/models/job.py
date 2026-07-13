from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.process import Process


class Job(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    process: Process
    recurring: bool = False
    cron: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    modified_at: datetime = Field(default_factory=datetime.now)
    modified_by: str = "system"
    active: bool = True
