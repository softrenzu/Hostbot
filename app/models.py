from enum import Enum
from dataclasses import dataclass


class IncidentState(str, Enum):
    NEW = "new"
    WIFI_SHARED = "wifi_shared"
    TROUBLESHOOTING = "troubleshooting"
    TICKET_CREATED = "ticket_created"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


@dataclass
class Property:
    id: str
    name: str
    public_data: dict
    private_data: dict


@dataclass
class Reservation:
    id: str
    property_id: str
    confirmation_code: str


@dataclass
class Incident:
    id: str
    reservation_id: str
    property_id: str
    category: str
    state: IncidentState = IncidentState.NEW
