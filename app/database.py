from __future__ import annotations

import os
from dataclasses import asdict

from sqlalchemy import JSON, String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .domain import (
    AuditEvent,
    Incident,
    IncidentState,
    JobStatus,
    JobType,
    KnowledgeDocument,
    OperationJob,
    Organization,
    Property,
    Reservation,
    Ticket,
)


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "hostbot_records"
    kind: Mapped[str] = mapped_column(String(40), primary_key=True)
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class PostgresRepository:
    """SQLAlchemy repository intended for PostgreSQL; SQLite works for tests."""

    def __init__(self, database_url: str | None = None):
        url = database_url or os.getenv("DATABASE_URL") or "sqlite+pysqlite:///:memory:"
        self.engine = create_engine(url, future=True)
        Base.metadata.create_all(self.engine)

    def _save(self, kind: str, obj, organization_id: str):
        row = Record(kind=kind, id=obj.id, organization_id=organization_id, payload=asdict(obj))
        with Session(self.engine) as session:
            session.merge(row)
            session.commit()
        return obj

    def _row(self, kind: str, record_id: str):
        with Session(self.engine) as session:
            return session.get(Record, {"kind": kind, "id": record_id})

    def _rows(self, kind: str, organization_id: str | None = None):
        statement = select(Record).where(Record.kind == kind)
        if organization_id:
            statement = statement.where(Record.organization_id == organization_id)
        with Session(self.engine) as session:
            return list(session.scalars(statement).all())

    def save_organization(self, obj):
        return self._save("organization", obj, obj.id)

    def save_property(self, obj):
        return self._save("property", obj, obj.organization_id)

    def save_reservation(self, obj):
        return self._save("reservation", obj, obj.organization_id)

    def save_incident(self, obj):
        return self._save("incident", obj, obj.organization_id)

    def save_ticket(self, obj):
        return self._save("ticket", obj, obj.organization_id)

    def save_document(self, obj):
        return self._save("document", obj, obj.organization_id)

    def save_job(self, obj):
        return self._save("job", obj, obj.organization_id)

    def log(self, event: AuditEvent):
        audit_id = f"{event.created_at}:{event.action}:{event.resource_id}"
        row = Record(kind="audit", id=audit_id, organization_id=event.organization_id, payload=asdict(event))
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
        return event

    def get_organization(self, record_id):
        row = self._row("organization", record_id)
        return Organization(**row.payload) if row else None

    def get_property(self, record_id):
        row = self._row("property", record_id)
        return Property(**row.payload) if row else None

    def get_reservation(self, record_id):
        row = self._row("reservation", record_id)
        return Reservation(**row.payload) if row else None

    def get_incident(self, record_id):
        row = self._row("incident", record_id)
        if not row:
            return None
        data = dict(row.payload)
        data["state"] = IncidentState(data["state"])
        return Incident(**data)

    def get_ticket(self, record_id):
        row = self._row("ticket", record_id)
        return Ticket(**row.payload) if row else None

    def get_job(self, record_id):
        row = self._row("job", record_id)
        if not row:
            return None
        data = dict(row.payload)
        data["type"] = JobType(data["type"])
        data["status"] = JobStatus(data["status"])
        return OperationJob(**data)

    def find_reservation(self, property_id, confirmation_code):
        for row in self._rows("reservation"):
            data = row.payload
            if data["property_id"] == property_id and data["confirmation_code"] == confirmation_code:
                return Reservation(**data)
        return None

    def active_incident(self, reservation_id, category):
        for row in self._rows("incident"):
            data = row.payload
            if data["reservation_id"] == reservation_id and data["category"] == category and data["state"] != "resolved":
                data = dict(data)
                data["state"] = IncidentState(data["state"])
                return Incident(**data)
        return None

    def ticket_for_incident(self, incident_id):
        for row in self._rows("ticket"):
            if row.payload["incident_id"] == incident_id:
                return Ticket(**row.payload)
        return None

    def list_documents(self, organization_id, property_id=None):
        result = []
        for row in self._rows("document", organization_id):
            item = KnowledgeDocument(**row.payload)
            if item.property_id is None or property_id is None or item.property_id == property_id:
                result.append(item)
        return result

    def list_tickets(self, organization_id):
        return [Ticket(**row.payload) for row in self._rows("ticket", organization_id)]

    def list_jobs(self, organization_id):
        result = []
        for row in self._rows("job", organization_id):
            data = dict(row.payload)
            data["type"] = JobType(data["type"])
            data["status"] = JobStatus(data["status"])
            result.append(OperationJob(**data))
        return result

    def list_audit(self, organization_id):
        return [AuditEvent(**row.payload) for row in self._rows("audit", organization_id)]
