"""Request and response models for the posting API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.validators import MAX_MESSAGE_LENGTH, extract_single_link, validate_message

EXAMPLE_MESSAGE = (
    "Check out our latest business platform and grow your online visibility. https://example.com"
)


class PostingRequest(BaseModel):
    message: str = Field(
        ...,
        description=f"Text to publish. Max {MAX_MESSAGE_LENGTH} characters, exactly one http(s) CTA link.",
        examples=[EXAMPLE_MESSAGE],
    )

    @field_validator("message")
    @classmethod
    def _check_message(cls, value: str) -> str:
        return validate_message(value)

    @property
    def link(self) -> str:
        return extract_single_link(self.message)


class PlatformResult(BaseModel):
    platform: str
    status: Literal["success", "failed"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = Field(None, description="Posting date (UTC), YYYY-MM-DD")
    time: str | None = Field(None, description="Posting time (UTC), HH:MM:SS")
    error: str | None = None


class PostingSummary(BaseModel):
    total: int
    succeeded: int
    failed: int


class PostingResponse(BaseModel):
    success: bool = Field(..., description="True when at least one platform published the message.")
    summary: PostingSummary
    results: list[PlatformResult]


class ValidationErrorItem(BaseModel):
    field: str
    message: str


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    errors: list[ValidationErrorItem]
