from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProcessType(StrEnum):
    BASH = "bash"
    PYTHON = "python"


class InlineProcessSource(BaseModel):
    kind: Literal["inline"] = "inline"
    content: str = Field(min_length=1, max_length=100_000)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class FileProcessSource(BaseModel):
    kind: Literal["file"] = "file"
    path: str = Field(min_length=1, max_length=1_000)

    @field_validator("path")
    @classmethod
    def require_relative_path(cls, value: str) -> str:
        path = Path(value.strip())
        if not value.strip():
            raise ValueError("must not be blank")
        if path.is_absolute():
            raise ValueError("must be relative to the configured script root")
        if ".." in path.parts:
            raise ValueError("must not contain parent-directory traversal")
        return str(path)


ProcessSource = Annotated[
    InlineProcessSource | FileProcessSource,
    Field(discriminator="kind"),
]


class ProcessCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: ProcessType
    source: ProcessSource

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class ProcessUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: ProcessType | None = None
    source: ProcessSource | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def require_a_change(self) -> "ProcessUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class Process(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    process_id: UUID = Field(default_factory=uuid4)
    type: ProcessType
    name: str
    source: ProcessSource
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str = "system"
    modified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modified_by: str = "system"
    last_run_at: datetime | None = None
