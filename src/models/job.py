from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from croniter import croniter
from pydantic import BaseModel, Field, field_validator, model_validator

from src.models.process import Process


JobArgument = Annotated[str, Field(max_length=1_000)]


def require_timezone(value: datetime | None) -> datetime | None:
    if value is not None and value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC) if value is not None else None


class JobCreate(BaseModel):
    process_id: UUID
    arguments: list[JobArgument] = Field(default_factory=list, max_length=50)
    recurring: bool = False
    cron: str | None = Field(default=None, max_length=120)
    next_run_at: datetime | None = None

    @field_validator("arguments")
    @classmethod
    def reject_null_bytes(cls, value: list[str]) -> list[str]:
        if any("\0" in argument for argument in value):
            raise ValueError("arguments must not contain null bytes")
        return value

    @field_validator("next_run_at")
    @classmethod
    def validate_timezone(cls, value: datetime | None) -> datetime | None:
        return require_timezone(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> "JobCreate":
        if self.recurring and not self.cron:
            raise ValueError("recurring jobs require a cron expression")
        if not self.recurring and self.cron is not None:
            raise ValueError("one-off jobs cannot have a cron expression")
        if self.cron and len(self.cron.split()) != 5:
            raise ValueError("cron expression must contain five fields")
        if self.cron and not croniter.is_valid(self.cron, strict=True):
            raise ValueError("cron expression is invalid or can never run")
        return self


class JobUpdate(BaseModel):
    active: bool | None = None
    next_run_at: datetime | None = None

    @field_validator("next_run_at")
    @classmethod
    def validate_timezone(cls, value: datetime | None) -> datetime | None:
        return require_timezone(value)

    @model_validator(mode="after")
    def require_a_change(self) -> "JobUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class Job(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    process: Process
    arguments: list[JobArgument] = Field(default_factory=list, max_length=50)
    recurring: bool = False
    cron: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "system"
    modified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modified_by: str = "system"
    active: bool = True
