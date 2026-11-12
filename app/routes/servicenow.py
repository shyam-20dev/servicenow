from fastapi import APIRouter, HTTPException

from ..schemas import ServiceNowCreate
from ..services import servicenow_service

router = APIRouter(prefix="/api/servicenow", tags=["ServiceNow (optional)"])


@router.get("/status")
def status():
    return servicenow_service.status()


@router.post("/test")
def test_connection():
    return servicenow_service.test_connection()


@router.post("/incidents")
def create_incident(body: ServiceNowCreate):
    result = servicenow_service.create_incident(body.incident_id)
    if result.get("not_found"):
        raise HTTPException(404, result["message"])
    return result   # HTTP 200 with ok=false on failure: the UI must show result["message"]
