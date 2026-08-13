from __future__ import annotations

import os
from dataclasses import asdict
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .core import HostbotService, seed_demo
from .database import PostgresRepository
from .domain import JobStatus, JobType, KnowledgeDocument, Organization, Property, Reservation
from .repository import MemoryRepository


def build_repository():
    if os.getenv("HOSTBOT_REPOSITORY", "memory").lower() == "postgres":
        return PostgresRepository()
    return MemoryRepository()


repo = build_repository()
seed_demo(repo)
service = HostbotService(repo)
app = FastAPI(title="Hostbot", version="0.2.0")


class StayRequest(BaseModel):
    property_id: str
    confirmation_code: str


class ChatRequest(BaseModel):
    property_id: str
    message: str
    stay_token: str | None = None


class OrganizationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class PropertyRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    name: str
    public_data: dict = {}
    private_data: dict = {}


class ReservationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    property_id: str
    confirmation_code: str
    guest_name: str = ""
    guest_contact: str = ""
    channel: str = "direct"
    external_id: str | None = None


class KnowledgeRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    property_id: str | None = None
    title: str
    body: str
    tags: list[str] = []


class JobRequest(BaseModel):
    organization_id: str
    property_id: str
    reservation_id: str | None = None
    type: JobType
    payload: dict = {}


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0", "repository": repo.__class__.__name__}


@app.post("/v1/stays/verify")
def verify_stay(request: StayRequest):
    result = service.verify_stay(request.property_id, request.confirmation_code)
    if not result:
        raise HTTPException(401, "invalid stay")
    return result


@app.get("/v1/properties/{property_id}/public")
def public_property(property_id: str):
    property_obj = repo.get_property(property_id)
    if not property_obj:
        raise HTTPException(404, "property not found")
    return property_obj.public_data


@app.get("/v1/properties/{property_id}/private")
def private_property(property_id: str, authorization: str | None = Header(default=None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    data = service.private_property(property_id, token)
    if data is None:
        raise HTTPException(403, "verified stay required")
    return data


@app.post("/v1/chat")
async def chat(request: ChatRequest):
    return await service.chat(request.property_id, request.message, request.stay_token)


@app.post("/v1/admin/organizations")
def add_organization(request: OrganizationRequest):
    return asdict(repo.save_organization(Organization(request.id, request.name)))


@app.post("/v1/admin/properties")
def add_property(request: PropertyRequest):
    obj = Property(request.id, request.organization_id, request.name, request.public_data, request.private_data)
    return asdict(repo.save_property(obj))


@app.post("/v1/admin/reservations")
def add_reservation(request: ReservationRequest):
    return asdict(repo.save_reservation(Reservation(**request.model_dump())))


@app.post("/v1/admin/knowledge")
def add_knowledge(request: KnowledgeRequest):
    return asdict(repo.save_document(KnowledgeDocument(**request.model_dump())))


@app.post("/v1/admin/jobs")
def add_job(request: JobRequest):
    job = service.create_job(
        request.organization_id,
        request.property_id,
        request.type,
        request.reservation_id,
        request.payload,
    )
    return asdict(job)


@app.patch("/v1/admin/jobs/{job_id}/{status}")
def update_job(job_id: str, status: JobStatus):
    return asdict(service.update_job(job_id, status))


@app.get("/v1/admin/{organization_id}/tickets")
def list_tickets(organization_id: str):
    return [asdict(item) for item in repo.list_tickets(organization_id)]


@app.get("/v1/admin/{organization_id}/jobs")
def list_jobs(organization_id: str):
    return [asdict(item) for item in repo.list_jobs(organization_id)]


@app.get("/v1/admin/{organization_id}/audit")
def list_audit(organization_id: str):
    return [asdict(item) for item in repo.list_audit(organization_id)]
