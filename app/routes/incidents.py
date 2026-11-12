from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas import IncidentCreate, IncidentUpdate, CATEGORIES, INCIDENT_STATUSES
from ..services import incident_service

router = APIRouter(prefix="/api/incidents", tags=["Incidents"])


@router.get("")
def list_incidents(status: Optional[str] = Query(None), category: Optional[str] = Query(None),
                   priority: Optional[int] = Query(None, ge=1, le=4), q: Optional[str] = Query(None, max_length=100)):
    if status and status not in INCIDENT_STATUSES:
        raise HTTPException(422, f"status must be one of {INCIDENT_STATUSES}")
    if category and category not in CATEGORIES:
        raise HTTPException(422, f"category must be one of {CATEGORIES}")
    return incident_service.list_incidents(status, category, priority, q)


@router.post("", status_code=201)
def create_incident(body: IncidentCreate):
    return incident_service.create_incident(body)


@router.get("/{incident_id}")
def get_incident(incident_id: int):
    incident = incident_service.get_incident(incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident


@router.patch("/{incident_id}")
def update_incident(incident_id: int, body: IncidentUpdate):
    incident = incident_service.update_incident(incident_id, body.status, body.assigned_to)
    if not incident:
        raise HTTPException(404, "Incident not found")
    return incident
