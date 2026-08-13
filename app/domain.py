from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentState(str, Enum):
    NEW = "new"
    WIFI_SHARED = "wifi_shared"
    TROUBLESHOOTING = "troubleshooting"
    TICKET_CREATED = "ticket_created"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class JobType(str, Enum):
    CLEANING = "cleaning"
    MAINTENANCE = "maintenance"


class JobStatus(str, Enum):
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    ACCEPTED = "accepted"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Organization:
    id: str
    name: str


@dataclass
class Property:
    id: str
    organization_id: str
    name: str
    public_data: dict[str, Any] = field(default_factory=dict)
    private_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Reservation:
    id: str
    organization_id: str
    property_id: str
    confirmation_code: str
    guest_name: str = ""
    guest_contact: str = ""
    channel: str = "direct"
    external_id: str | None = None


@dataclass
class Incident:
    id: str
    organization_id: str
    reservation_id: str
    property_id: str
    category: str
    state: IncidentState = IncidentState.NEW


@dataclass
class Ticket:
    id: str
    organization_id: str
    incident_id: str
    property_id: str
    status: str = "created"
    assignee: str | None = None


@dataclass
class KnowledgeDocument:
    id: str
    organization_id: str
    property_id: str | None
    title: str
    body: str
    tags: list[str] = field(default_factory=list)


@dataclass
class OperationJob:
    id: str
    organization_id: str
    property_id: str
    reservation_id: str | None
    type: JobType
    status: JobStatus = JobStatus.QUEUED
    payload: dict[str, Any] = field(default_factory=dict)
    external_id: str | None = None


@dataclass
class AuditEvent:
    action: str
    organization_id: str
    resource_id: str
    actor: str
    created_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
