from uuid import uuid4
from .models import Incident, IncidentState
from .policy import Decision, policy
from .store import Ticket, Store
from .workflow import advance


class HostbotService:
    def __init__(self, store: Store):
        self.store = store

    def verify_stay(self, property_id: str, confirmation_code: str) -> dict | None:
        for reservation in self.store.reservations.values():
            if reservation.property_id == property_id and reservation.confirmation_code == confirmation_code:
                return {
                    "reservation_id": reservation.id,
                    "property_id": reservation.property_id,
                    "stay_token": self.store.issue_stay_token(reservation),
                }
        self.store.log("stay.verify.denied", property_id)
        return None

    def public_property(self, property_id: str) -> dict | None:
        property_obj = self.store.properties.get(property_id)
        return property_obj.public_data if property_obj else None

    def chat(self, property_id: str, message: str, stay_token: str | None = None) -> dict:
        property_obj = self.store.properties.get(property_id)
        if not property_obj:
            return {"error": "property not found"}

        reservation = self.store.resolve_stay_token(stay_token, property_id)
        text = message.lower()
        is_network_issue = any(word in text for word in ["internet", "wifi", "wi-fi", "network", "ネット", "つなが", "繋が"])

        if is_network_issue:
            decision = policy.decide("create_guest_ticket", stay_verified=reservation is not None)
            if decision.decision != Decision.ALLOW:
                return {"reply": "Please verify your reservation before starting a property support workflow."}
            incident = self._active_incident(reservation.id, property_id)
            if incident.state == IncidentState.NEW:
                advance(incident, IncidentState.WIFI_SHARED)
                return {"reply": "Please review the property network instructions and reconnect. If the issue continues, message me again.", "incident_id": incident.id, "state": incident.state.value}
            if incident.state == IncidentState.WIFI_SHARED:
                advance(incident, IncidentState.TROUBLESHOOTING)
                return {"reply": "Please follow the property network restart procedure and test again. If it still fails, message me again.", "incident_id": incident.id, "state": incident.state.value}
            if incident.state == IncidentState.TROUBLESHOOTING:
                ticket = self._ticket(incident)
                advance(incident, IncidentState.TICKET_CREATED)
                return {"reply": "A support ticket has been created for the operations team.", "incident_id": incident.id, "ticket_id": ticket.id, "state": incident.state.value}
            ticket = self._ticket(incident)
            return {"reply": f"Your support case is {incident.state.value}.", "incident_id": incident.id, "ticket_id": ticket.id, "state": incident.state.value}

        public = property_obj.public_data
        if "check" in text and "out" in text:
            return {"reply": f"Check-out is {public['check_out']}."}
        if "check" in text and "in" in text:
            return {"reply": f"Check-in is {public['check_in']}."}
        if "bed" in text:
            return {"reply": f"Beds: {public['beds']}."}
        return {"reply": "I can answer public stay questions and start verified support workflows."}

    def _active_incident(self, reservation_id: str, property_id: str) -> Incident:
        for incident in self.store.incidents.values():
            if incident.reservation_id == reservation_id and incident.property_id == property_id and incident.category == "internet" and incident.state != IncidentState.RESOLVED:
                return incident
        incident = Incident(id=str(uuid4()), reservation_id=reservation_id, property_id=property_id, category="internet")
        self.store.incidents[incident.id] = incident
        self.store.log("incident.created", incident.id)
        return incident

    def _ticket(self, incident: Incident) -> Ticket:
        for ticket in self.store.tickets.values():
            if ticket.incident_id == incident.id:
                return ticket
        ticket = Ticket(id=str(uuid4()), incident_id=incident.id, property_id=incident.property_id)
        self.store.tickets[ticket.id] = ticket
        self.store.log("ticket.created", ticket.id)
        return ticket
