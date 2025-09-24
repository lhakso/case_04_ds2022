from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field, conint, constr, validator


def hash_text(value: str) -> str:
    """Return the SHA-256 hex digest for the provided text."""
    return sha256(value.encode("utf-8")).hexdigest()


def compute_submission_id(email: str, timestamp: datetime) -> str:
    """Create a stable submission identifier derived from email and hour bucket."""
    bucket = timestamp.strftime("%Y%m%d%H")
    return hash_text(email + bucket)


class SurveySubmission(BaseModel):
    name: constr(min_length=1) = Field(..., description="Respondent name")
    email: EmailStr = Field(..., description="Respondent email address")
    age: conint(ge=0, le=130) = Field(..., description="Respondent age in years")
    consent: bool = Field(..., description="Whether respondent granted consent")
    rating: conint(ge=1, le=5) = Field(..., description="Satisfaction rating 1-5")
    comments: constr(strip_whitespace=True, min_length=0) = Field(
        "", description="Optional free-form feedback"
    )
    user_agent: Optional[str] = Field(
        None, description="Client user-agent string if supplied"
    )
    submission_id: Optional[str] = Field(
        None, description="Unique submission identifier"
    )

    class Config:
        anystr_strip_whitespace = True
        orm_mode = False

    @validator("comments", pre=True, always=True)
    def _default_comments(cls, value: Optional[str]) -> str:
        return value or ""

    def to_storage_record(self, timestamp: datetime) -> Dict[str, Any]:
        email_normalized = str(self.email).lower()
        submission_id = self.submission_id or compute_submission_id(
            email_normalized, timestamp
        )

        record: Dict[str, Any] = {
            "submission_id": submission_id,
            "name": self.name,
            "consent": self.consent,
            "rating": self.rating,
            "comments": self.comments,
            "email": hash_text(email_normalized),
            "age": hash_text(str(self.age)),
            "received_at": timestamp.isoformat(),
        }

        if self.user_agent:
            record["user_agent"] = self.user_agent

        return record
