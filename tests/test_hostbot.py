from app.hostbot import HostbotService
from app.store import build_demo_store


def test_verified_network_incident_creates_ticket_in_order():
    store = build_demo_store()
    service = HostbotService(store)

    verified = service.verify_stay("demo-tokyo", "HBDEMO2026")
    assert verified is not None
    token = verified["stay_token"]

    first = service.chat("demo-tokyo", "wifi is not working", token)
    second = service.chat("demo-tokyo", "internet still has a problem", token)
    third = service.chat("demo-tokyo", "network still does not work", token)

    assert first["state"] == "wifi_shared"
    assert second["state"] == "troubleshooting"
    assert third["state"] == "ticket_created"
    assert third["ticket_id"] in store.tickets


def test_unverified_guest_cannot_start_support_workflow():
    store = build_demo_store()
    service = HostbotService(store)
    result = service.chat("demo-tokyo", "wifi is not working")
    assert "verify" in result["reply"].lower()
