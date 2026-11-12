"""Pydantic models: request validation and AI-output validation."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

CATEGORIES = ["Network", "Hardware", "Software", "Access", "Other"]
INCIDENT_STATUSES = ["New", "In Progress", "Resolved", "Closed"]
REQUEST_STATUSES = ["Submitted", "Approved", "In Progress", "Fulfilled", "Rejected"]
DEPARTMENTS = ["IT", "HR", "Finance", "Facilities"]

# Service catalog: the SAME request workflow is reused by every department.
REQUEST_CATALOG = {
    "IT": ["Software installation", "Hardware request", "Access request", "Account creation"],
    "HR": ["New joiner onboarding", "Leave policy query", "Employment letter", "Payroll data change"],
    "Finance": ["Expense reimbursement", "Purchase approval", "Invoice query", "Budget code request"],
    "Facilities": ["Desk / seat allocation", "Meeting room setup", "Access card request", "Maintenance request"],
}


class AIAnalysis(BaseModel):
    """What we REQUIRE from the LLM. Anything else is rejected and we fall back."""

    summary: str = Field(min_length=3, max_length=400)
    category: str
    impact: int = Field(ge=1, le=3)
    urgency: int = Field(ge=1, le=3)
    troubleshooting_steps: List[str] = Field(min_length=1, max_length=10)
    recommended_resolution: str = Field(min_length=3, max_length=1200)

    @field_validator("category")
    @classmethod
    def _normalise_category(cls, v: str) -> str:
        for c in CATEGORIES:
            if v.strip().lower() == c.lower():
                return c
        return "Other"

    @field_validator("troubleshooting_steps", mode="before")
    @classmethod
    def _steps_to_strings(cls, v):
        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        return v


class IncidentCreate(BaseModel):
    short_description: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    reporter: str = Field(default="demo.employee", min_length=2, max_length=80)
    # Optional: if omitted, the AI (or rules) suggests impact/urgency.
    impact: Optional[int] = Field(default=None, ge=1, le=3)
    urgency: Optional[int] = Field(default=None, ge=1, le=3)


class IncidentUpdate(BaseModel):
    status: Optional[Literal["New", "In Progress", "Resolved", "Closed"]] = None
    assigned_to: Optional[str] = Field(default=None, max_length=80)


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=1000)
    session_id: str = Field(default="demo-session", min_length=1, max_length=64)


class RequestCreate(BaseModel):
    department: Literal["IT", "HR", "Finance", "Facilities"]
    request_type: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=3000)
    requester: str = Field(default="demo.employee", min_length=2, max_length=80)
    priority: Literal["Low", "Medium", "High"] = "Medium"

    @field_validator("request_type")
    @classmethod
    def _type_in_catalog(cls, v, info):
        dept = info.data.get("department")
        if dept and v not in REQUEST_CATALOG[dept]:
            raise ValueError(f"'{v}' is not in the {dept} service catalog")
        return v


class RequestUpdate(BaseModel):
    status: Literal["Submitted", "Approved", "In Progress", "Fulfilled", "Rejected"]


class ServiceNowCreate(BaseModel):
    incident_id: int = Field(ge=1)
