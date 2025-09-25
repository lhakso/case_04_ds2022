from datetime import datetime
from hashlib import sha256
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, EmailStr, validator


def hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def compute_submission_id(email: str, timestamp: datetime) -> str:
    bucket = timestamp.strftime("%Y%m%d%H")
    return hash_text(email + bucket)


class SurveySubmission(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(..., ge=13, le=120)
    consent: bool = Field(..., description="Must be true to accept")
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = Field("", max_length=1000)
    source: Optional[str] = Field(
        "other", description="web|mobile|other; default other"
    )
    user_agent: Optional[str] = Field(None)
    submission_id: Optional[str] = Field(None)

    class Config:
        anystr_strip_whitespace = True

    @validator("comments", pre=True, always=True)
    def _default_comments(cls, v: Optional[str]) -> str:
        return (v or "").strip()

    @validator("source", pre=True, always=True)
    def _normalize_source(cls, v: Optional[str]) -> str:
        if not v:
            return "other"
        s = str(v).strip().lower()
        return s if s in {"web", "mobile", "other"} else "other"

    @validator("consent")
    def _must_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("consent must be true")
        return v

    def to_storage_record(
        self, timestamp: datetime, ip: Optional[str] = None
    ) -> Dict[str, Any]:
        email_norm = str(self.email).lower()
        sub_id = self.submission_id or compute_submission_id(email_norm, timestamp)
        record: Dict[str, Any] = {
            "submission_id": sub_id,
            "name": self.name,
            "consent": self.consent,
            "rating": self.rating,
            "comments": self.comments,
            "source": self.source or "other",
            "email": hash_text(email_norm),
            "age": hash_text(str(self.age)),
            "received_at": timestamp.isoformat(),
        }
        if self.user_agent:
            record["user_agent"] = self.user_agent
        if ip:
            record["ip"] = ip
        return record
