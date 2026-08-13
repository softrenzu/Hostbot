from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import secrets
from .models import Incident, IncidentState, Property, Reservation


@dataclass
class Ticket:
    id: str
    incident_id: str
    property_id: str
    status: str = "created"


@dataclass
class AuditEvent:
    action: str
    resource_id: str
    created_at: str


@dataclass
class Store:
    properties: dict[str, Property] = field(default_factory=dict)
    reservations: dict[str, Reservation] = field(default_factory=dict)
    stay_tokens: dict[str, tuple[str, str, datetime]] = field(default_factory=dict)
    incidents: dict[str, Incident] = field(default_factory=dict)
    tickets: dict[str, Ticket] = field(default_factory=dict)
    audit: list[AuditEvent] = field(default_factory=list)

    def issue_stay_token(self, reservation: Reservation) -> str:
        token = secrets.token_urlsafe(32)
        self.stay_tokens[token] = (
            reservation.id,
            reservation.property_id,
            datetime.now(timezone.utc) + timedelta(hours=12),
        )
        self.log("stay.verify.allowed", reservation.id)
        return token

    def resolve_stay_token(self, token: str | None, property_id: str) -> Reservation | None:
        if not token or token not in self.stay_tokens:
            return None
        reservation_id, token_property_id, expires_at = self.stay_tokens[token]
        if token_property_id != property_id or expires_at < datetime.now(timezone.utc):
            return None
        return self.reservations.get(reservation_id)

    def log(self, action: str, resource_id: str) -> None:
        self.audit.append(AuditEvent(action, resource_id, datetime.now(timezone.utc).isoformat()))


def build_demo_store() -> Store:
    store = Store()
    store.properties["demo-tokyo"] = Property(
        id="demo-tokyo",
        name="Hostbot Demo Tokyo",
        public_data={
            "check_in": "15:00",
            "check_out": "10:00",
            "beds": "2 double beds",
            "pets": "not allowed",
            "house_rules": "No smoking. Keep noise low after 22:00.",
        },
        private_data={
            "wifi_ssid": "HOSTBOT-DEMO",
            "wifi_password": "demo-password",
            "lockbox_code": "1234",
            "internet_troubleshooting": "Unplug the router for 20 seconds, reconnect it, wait 2 minutes, and test again.",
        },
    )
    store.reservations["demo-reservation"] = Reservation(
        id="demo-reservation",
        property_id="demo-tokyo",
        confirmation_code="HBDEMO2026",
    )
    return store


store = build_demo_store()
