from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ProcessType(str, Enum):
    BASH = "bash"
    PYTHON = "python"


class Process(BaseModel):
    process_id: UUID = Field(default_factory=uuid4)
    type: ProcessType
    name: str
    script: str
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    modified_at: datetime = Field(default_factory=datetime.now)
    modified_by: str = "system"
    last_run_at: datetime | None = None
