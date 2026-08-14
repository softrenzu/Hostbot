from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .domain import AuditEvent, Incident, JobType, KnowledgeDocument, OperationJob, Organization, Property, Reservation, Ticket


class MemoryRepository:
    def __init__(self):
        self.organizations: dict[str, Organization] = {}
        self.properties: dict[str, Property] = {}
        self.reservations: dict[str, Reservation] = {}
        self.incidents: dict[str, Incident] = {}
        self.tickets: dict[str, Ticket] = {}
        self.documents: dict[str, KnowledgeDocument] = {}
        self.jobs: dict[str, OperationJob] = {}
        self.audit: list[AuditEvent] = []

    def save_organization(self, obj: Organization): self.organizations[obj.id] = obj; return obj
    def save_property(self, obj: Property): self.properties[obj.id] = obj; return obj
    def save_reservation(self, obj: Reservation): self.reservations[obj.id] = obj; return obj
    def save_incident(self, obj: Incident): self.incidents[obj.id] = obj; return obj
    def save_ticket(self, obj: Ticket): self.tickets[obj.id] = obj; return obj
    def save_document(self, obj: KnowledgeDocument): self.documents[obj.id] = obj; return obj
    def save_job(self, obj: OperationJob): self.jobs[obj.id] = obj; return obj
    def log(self, event: AuditEvent): self.audit.append(event); return event

    def get_organization(self, organization_id: str): return self.organizations.get(organization_id)
    def get_property(self, property_id: str): return self.properties.get(property_id)
    def get_reservation(self, reservation_id: str): return self.reservations.get(reservation_id)
    def get_incident(self, incident_id: str): return self.incidents.get(incident_id)
    def get_ticket(self, ticket_id: str): return self.tickets.get(ticket_id)
    def get_job(self, job_id: str): return self.jobs.get(job_id)

    def find_reservation(self, property_id: str, confirmation_code: str):
        return next((r for r in self.reservations.values() if r.property_id == property_id and r.confirmation_code == confirmation_code), None)

    def find_reservation_by_external(self, organization_id: str, channel: str, external_id: str):
        return next((r for r in self.reservations.values() if r.organization_id == organization_id and r.channel == channel and r.external_id == external_id), None)

    def active_incident(self, reservation_id: str, category: str):
        return next((i for i in self.incidents.values() if i.reservation_id == reservation_id and i.category == category and i.state.value != "resolved"), None)

    def ticket_for_incident(self, incident_id: str):
        return next((t for t in self.tickets.values() if t.incident_id == incident_id), None)

    def job_for_reservation(self, reservation_id: str, job_type: JobType):
        return next((j for j in self.jobs.values() if j.reservation_id == reservation_id and j.type == job_type), None)

    def list_documents(self, organization_id: str, property_id: str | None = None) -> Iterable[KnowledgeDocument]:
        return [d for d in self.documents.values() if d.organization_id == organization_id and (d.property_id is None or property_id is None or d.property_id == property_id)]

    def list_tickets(self, organization_id: str): return [t for t in self.tickets.values() if t.organization_id == organization_id]
    def list_jobs(self, organization_id: str): return [j for j in self.jobs.values() if j.organization_id == organization_id]
    def list_audit(self, organization_id: str): return [e for e in self.audit if e.organization_id == organization_id]

    def snapshot(self) -> dict:
        return {
            "organizations": [asdict(x) for x in self.organizations.values()],
            "properties": [asdict(x) for x in self.properties.values()],
            "reservations": [asdict(x) for x in self.reservations.values()],
            "tickets": [asdict(x) for x in self.tickets.values()],
            "jobs": [asdict(x) for x in self.jobs.values()],
        }
