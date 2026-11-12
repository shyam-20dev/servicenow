from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas import DEPARTMENTS, REQUEST_CATALOG, REQUEST_STATUSES, RequestCreate, RequestUpdate
from ..services import request_service

router = APIRouter(prefix="/api/requests", tags=["Service Requests"])


@router.get("/catalog")
def catalog():
    """The service catalog: the same workflow is offered by every department."""
    return {"departments": DEPARTMENTS, "catalog": REQUEST_CATALOG, "statuses": REQUEST_STATUSES,
            "groups": request_service.GROUP_FOR_DEPARTMENT}


@router.get("")
def list_requests(department: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    if department and department not in DEPARTMENTS:
        raise HTTPException(422, f"department must be one of {DEPARTMENTS}")
    if status and status not in REQUEST_STATUSES:
        raise HTTPException(422, f"status must be one of {REQUEST_STATUSES}")
    return request_service.list_requests(department, status)


@router.post("", status_code=201)
def create_request(body: RequestCreate):
    return request_service.create_request(body)


@router.patch("/{request_id}")
def update_request(request_id: int, body: RequestUpdate):
    row = request_service.update_request(request_id, body.status)
    if not row:
        raise HTTPException(404, "Service request not found")
    return row
