from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RecipientInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=150)
    email: EmailStr


class CertificateJobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    certificate_title: str = Field(min_length=1, max_length=200)
    organization: str = Field(min_length=1, max_length=200)
    issue_date: date

    # Validate each recipient separately in the API logic.
    recipients: list[Any] = Field(min_length=1, max_length=500)