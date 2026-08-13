from .models import Incident, IncidentState

ALLOWED_NEXT = {
    IncidentState.NEW: IncidentState.WIFI_SHARED,
    IncidentState.WIFI_SHARED: IncidentState.TROUBLESHOOTING,
    IncidentState.TROUBLESHOOTING: IncidentState.TICKET_CREATED,
    IncidentState.TICKET_CREATED: IncidentState.IN_PROGRESS,
    IncidentState.IN_PROGRESS: IncidentState.RESOLVED,
}


def advance(incident: Incident, target: IncidentState) -> bool:
    if ALLOWED_NEXT.get(incident.state) != target:
        return False
    incident.state = target
    return True
