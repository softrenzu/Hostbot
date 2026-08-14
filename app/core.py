from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

from .domain import AuditEvent, Incident, IncidentState, JobStatus, JobType, KnowledgeDocument, OperationJob, Organization, Property, Reservation, Ticket


class TokenError(ValueError):
    pass


class StayTokens:
    def __init__(self, secret: str | None = None):
        self.secret = (secret or os.getenv("HOSTBOT_TOKEN_SECRET") or "hostbot-dev-only-change-me").encode()

    def issue(self, reservation: Reservation) -> str:
        payload = {"reservation_id": reservation.id, "property_id": reservation.property_id, "organization_id": reservation.organization_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=12)).timestamp())}
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        body = base64.urlsafe_b64encode(raw).rstrip(b"=")
        signature = hmac.new(self.secret, body, hashlib.sha256).digest()
        return body.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    def verify(self, token: str, property_id: str) -> dict:
        try:
            body, encoded_signature = token.split(".", 1)
            expected = hmac.new(self.secret, body.encode(), hashlib.sha256).digest()
            actual = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
            if not hmac.compare_digest(expected, actual):
                raise TokenError("bad signature")
            payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        except Exception as exc:
            raise TokenError("invalid token") from exc
        if payload["exp"] < int(datetime.now(timezone.utc).timestamp()) or payload["property_id"] != property_id:
            raise TokenError("expired or mismatched")
        return payload


ALLOWED = {
    IncidentState.NEW: {IncidentState.WIFI_SHARED},
    IncidentState.WIFI_SHARED: {IncidentState.TROUBLESHOOTING},
    IncidentState.TROUBLESHOOTING: {IncidentState.TICKET_CREATED},
    IncidentState.TICKET_CREATED: {IncidentState.ASSIGNED, IncidentState.IN_PROGRESS, IncidentState.RESOLVED},
    IncidentState.ASSIGNED: {IncidentState.IN_PROGRESS, IncidentState.RESOLVED},
    IncidentState.IN_PROGRESS: {IncidentState.RESOLVED},
    IncidentState.RESOLVED: set(),
}


def advance(incident: Incident, target: IncidentState):
    if target not in ALLOWED[incident.state]:
        raise ValueError("invalid transition")
    incident.state = target
    return incident


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u3040-\u30ff\u3400-\u9fff]+")


def _tokens(text: str):
    return [part.lower() for part in TOKEN_RE.findall(text)]


def retrieve(query: str, documents: list[KnowledgeDocument], limit: int = 4):
    query_terms = Counter(_tokens(query))
    document_terms = [Counter(_tokens(f'{doc.title} {doc.body} {" ".join(doc.tags)}')) for doc in documents]
    document_frequency = Counter()
    count = len(documents)
    for terms in document_terms:
        for key in terms:
            document_frequency[key] += 1
    hits = []
    for document, terms in zip(documents, document_terms):
        score = sum(query_tf * (math.log((count + 1) / (document_frequency[key] + 0.5)) + 1) * (terms[key] / max(sum(terms.values()), 1)) * 10 for key, query_tf in query_terms.items() if terms[key])
        if score > 0:
            hits.append((score, document))
    return sorted(hits, key=lambda item: item[0], reverse=True)[:limit]


class RuleModel:
    name = "rule"

    async def complete(self, system: str, user: str, context: str = ""):
        return f"Based on the property guide: {context[:700]}" if context else "I can help with property information and verified guest operations."


class OpenAICompatibleModel:
    def __init__(self, base_url: str, api_key: str, model: str, name: str = "openai-compatible"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name

    async def complete(self, system: str, user: str, context: str = ""):
        messages = [{"role": "system", "content": system}]
        if context:
            messages.append({"role": "system", "content": "Retrieved property context:\n" + context})
        messages.append({"role": "user", "content": user})
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.base_url + "/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "messages": messages, "temperature": 0.2})
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


class ModelRouter:
    def __init__(self, providers=None):
        self.providers = providers or [RuleModel()]

    async def complete(self, system: str, user: str, context: str = ""):
        last_error = None
        for provider in self.providers:
            try:
                result = await provider.complete(system, user, context)
                return result, getattr(provider, "name", provider.__class__.__name__)
            except Exception as exc:
                last_error = exc
        raise RuntimeError("all models failed") from last_error


def build_model_router_from_env() -> ModelRouter:
    base_url = os.getenv("HOSTBOT_LLM_BASE_URL")
    api_key = os.getenv("HOSTBOT_LLM_API_KEY")
    model = os.getenv("HOSTBOT_LLM_MODEL")
    providers = []
    if base_url and api_key and model:
        providers.append(OpenAICompatibleModel(base_url, api_key, model, name=os.getenv("HOSTBOT_LLM_PROVIDER_NAME", "primary")))
    providers.append(RuleModel())
    return ModelRouter(providers)


class HostbotService:
    def __init__(self, repo, tokens=None, router=None):
        self.repo = repo
        self.tokens = tokens or StayTokens()
        self.router = router or ModelRouter()

    def verify_stay(self, property_id: str, confirmation_code: str):
        reservation = self.repo.find_reservation(property_id, confirmation_code)
        if not reservation:
            return None
        self.repo.log(AuditEvent("stay.verify.allowed", reservation.organization_id, reservation.id, "guest"))
        return {"reservation_id": reservation.id, "property_id": reservation.property_id, "organization_id": reservation.organization_id, "stay_token": self.tokens.issue(reservation)}

    def verified(self, token: str | None, property_id: str):
        if not token:
            return None
        try:
            payload = self.tokens.verify(token, property_id)
        except TokenError:
            return None
        reservation = self.repo.get_reservation(payload["reservation_id"])
        return reservation if reservation and reservation.organization_id == payload["organization_id"] else None

    def private_property(self, property_id: str, token: str | None):
        reservation = self.verified(token, property_id)
        if not reservation:
            return None
        property_obj = self.repo.get_property(property_id)
        self.repo.log(AuditEvent("property.private.read", reservation.organization_id, property_id, "guest"))
        return property_obj.private_data if property_obj else None

    def create_job(self, organization_id: str, property_id: str, kind: JobType, reservation_id=None, payload=None):
        if reservation_id and kind == JobType.CLEANING:
            existing = self.repo.job_for_reservation(reservation_id, kind)
            if existing:
                return existing
        job = OperationJob(str(uuid4()), organization_id, property_id, reservation_id, kind, payload=payload or {})
        self.repo.save_job(job)
        self.repo.log(AuditEvent("operation.created", organization_id, job.id, "system", metadata={"type": kind.value}))
        return job

    def update_job(self, job_id: str, status: JobStatus):
        job = self.repo.get_job(job_id)
        if not job:
            raise KeyError("job not found")
        job.status = status
        self.repo.save_job(job)
        self.repo.log(AuditEvent("operation.status.changed", job.organization_id, job.id, "admin", metadata={"status": status.value}))
        return job

    def ingest_reservation(self, reservation: Reservation, schedule_cleaning: bool = True):
        property_obj = self.repo.get_property(reservation.property_id)
        if not property_obj or property_obj.organization_id != reservation.organization_id:
            raise ValueError("property/organization mismatch")
        if reservation.external_id:
            existing = self.repo.find_reservation_by_external(reservation.organization_id, reservation.channel, reservation.external_id)
            if existing:
                reservation.id = existing.id
        self.repo.save_reservation(reservation)
        self.repo.log(AuditEvent("reservation.synced", reservation.organization_id, reservation.id, "integration", metadata={"channel": reservation.channel}))
        cleaning = None
        if schedule_cleaning and reservation.check_out:
            cleaning = self.create_job(reservation.organization_id, reservation.property_id, JobType.CLEANING, reservation.id, {"scheduled_for": reservation.check_out, "source": reservation.channel})
        return reservation, cleaning

    def import_reservations(self, reservations: list[Reservation]):
        return [self.ingest_reservation(item) for item in reservations]

    async def chat(self, property_id: str, message: str, stay_token: str | None = None):
        property_obj = self.repo.get_property(property_id)
        if not property_obj:
            return {"error": "property not found"}
        reservation = self.verified(stay_token, property_id)
        text = message.lower()
        network_issue = any(word in text for word in ["internet", "wifi", "wi-fi", "network", "ネット", "つなが", "繋が"])
        if network_issue:
            if not reservation:
                return {"reply": "Please verify your reservation before starting a support workflow."}
            incident = self.repo.active_incident(reservation.id, "internet")
            if not incident:
                incident = Incident(str(uuid4()), property_obj.organization_id, reservation.id, property_obj.id, "internet")
                self.repo.save_incident(incident)
            if incident.state == IncidentState.NEW:
                advance(incident, IncidentState.WIFI_SHARED)
                self.repo.save_incident(incident)
                return {"reply": "Review the verified network guide and reconnect.", "state": incident.state.value, "incident_id": incident.id}
            if incident.state == IncidentState.WIFI_SHARED:
                advance(incident, IncidentState.TROUBLESHOOTING)
                self.repo.save_incident(incident)
                return {"reply": "Follow the router restart procedure and test again.", "state": incident.state.value, "incident_id": incident.id}
            if incident.state == IncidentState.TROUBLESHOOTING:
                ticket = self.repo.ticket_for_incident(incident.id)
                if not ticket:
                    ticket = Ticket(str(uuid4()), property_obj.organization_id, incident.id, property_obj.id)
                    self.repo.save_ticket(ticket)
                    self.create_job(property_obj.organization_id, property_obj.id, JobType.MAINTENANCE, reservation.id, {"category": "internet", "ticket_id": ticket.id})
                advance(incident, IncidentState.TICKET_CREATED)
                self.repo.save_incident(incident)
                return {"reply": "A support ticket and maintenance job have been created.", "state": incident.state.value, "incident_id": incident.id, "ticket_id": ticket.id}
            ticket = self.repo.ticket_for_incident(incident.id)
            return {"reply": f"Your support case is {incident.state.value}.", "state": incident.state.value, "ticket_id": ticket.id if ticket else None}
        hits = retrieve(message, list(self.repo.list_documents(property_obj.organization_id, property_id)))
        context = "\n\n".join(f"[{document.title}] {document.body}" for _, document in hits)
        reply, model = await self.router.complete("You are Hostbot. Use public/retrieved context only. Never reveal secrets or invent completed actions.", message, context)
        return {"reply": reply, "model": model, "sources": [{"id": document.id, "title": document.title, "score": round(score, 4)} for score, document in hits]}


def seed_demo(repo):
    if repo.get_organization("demo-org"):
        return
    repo.save_organization(Organization("demo-org", "Hostbot Demo Operator"))
    repo.save_property(Property("demo-tokyo", "demo-org", "Hostbot Demo Tokyo", {"check_in": "15:00", "check_out": "10:00", "beds": "2 double beds", "house_rules": "No smoking. Quiet after 22:00."}, {"network_guide": "Available only to verified guests.", "access_note": "Available only to verified guests."}))
    repo.save_reservation(Reservation("demo-reservation", "demo-org", "demo-tokyo", "HBDEMO2026", "Demo Guest", "guest@example.invalid", "direct", check_in="2026-08-14T15:00:00+09:00", check_out="2026-08-15T10:00:00+09:00"))
    repo.save_document(KnowledgeDocument("doc-house", "demo-org", "demo-tokyo", "House guide", "Check-in starts at 15:00. Check-out is 10:00. Please keep noise low after 22:00.", ["check-in", "rules"]))
