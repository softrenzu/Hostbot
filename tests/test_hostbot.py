import asyncio

from fastapi.testclient import TestClient

from app.core import HostbotService, OpenAICompatibleModel, StayTokens, TokenError, build_model_router_from_env, seed_demo
from app.database import PostgresRepository
from app.domain import JobType, KnowledgeDocument, Organization, Property, Reservation
from app.main import app
from app.repository import MemoryRepository


def make():
    repo = MemoryRepository(); seed_demo(repo); return repo, HostbotService(repo, StayTokens("test-secret"))


def test_flow_and_maintenance_job():
    repo, service = make(); token = service.verify_stay("demo-tokyo", "HBDEMO2026")["stay_token"]
    first = asyncio.run(service.chat("demo-tokyo", "wifi broken", token)); second = asyncio.run(service.chat("demo-tokyo", "internet still broken", token)); third = asyncio.run(service.chat("demo-tokyo", "network still broken", token))
    assert [first["state"], second["state"], third["state"]] == ["wifi_shared", "troubleshooting", "ticket_created"]
    assert len(repo.tickets) == 1 and len(repo.jobs) == 1 and next(iter(repo.jobs.values())).type.value == "maintenance"


def test_unverified_denied():
    _, service = make(); assert "verify" in asyncio.run(service.chat("demo-tokyo", "wifi broken"))["reply"].lower()


def test_private_scope_and_tenant_rag():
    repo, service = make(); token = service.verify_stay("demo-tokyo", "HBDEMO2026")["stay_token"]; assert service.private_property("demo-tokyo", token)
    repo.save_organization(Organization("o2", "O2")); repo.save_property(Property("p2", "o2", "P2")); repo.save_document(KnowledgeDocument("secret", "o2", "p2", "Secret", "ZXQ secret phrase", []))
    result = asyncio.run(service.chat("demo-tokyo", "ZXQ secret phrase")); assert not any(source["id"] == "secret" for source in result["sources"])


def test_token_tamper_rejected():
    manager = StayTokens("x"); repo = MemoryRepository(); seed_demo(repo); token = manager.issue(repo.get_reservation("demo-reservation"))
    try:
        manager.verify(token + "x", "demo-tokyo"); assert False
    except TokenError:
        pass


def test_reservation_import_schedules_one_cleaning_job_and_deduplicates():
    repo, service = make()
    reservation = Reservation("import-1", "demo-org", "demo-tokyo", "IMPORT1", channel="beds24", external_id="beds-123", check_out="2026-08-20T10:00:00+09:00")
    saved, job = service.ingest_reservation(reservation); assert job is not None and job.type.value == "cleaning" and job.payload["scheduled_for"] == reservation.check_out
    second = Reservation("different-local-id", "demo-org", "demo-tokyo", "IMPORT1", channel="beds24", external_id="beds-123", check_out="2026-08-20T10:00:00+09:00")
    saved_again, job_again = service.ingest_reservation(second)
    assert saved_again.id == saved.id and job_again.id == job.id and len([item for item in repo.jobs.values() if item.type.value == "cleaning"]) == 1


def test_sqlalchemy_repository_roundtrip_and_cleaning_lookup():
    repo = PostgresRepository("sqlite+pysqlite:///:memory:"); seed_demo(repo); service = HostbotService(repo, StayTokens("test-secret"))
    reservation = Reservation("sql-import", "demo-org", "demo-tokyo", "SQLIMPORT", channel="booking.com", external_id="booking-456", check_out="2026-08-21T10:00:00+09:00")
    service.ingest_reservation(reservation); found = repo.find_reservation_by_external("demo-org", "booking.com", "booking-456"); assert found and found.id == "sql-import"
    cleaning = repo.job_for_reservation("sql-import", JobType.CLEANING); assert cleaning and cleaning.payload["scheduled_for"] == reservation.check_out


def test_model_router_wires_openai_compatible_provider_from_environment(monkeypatch):
    monkeypatch.setenv("HOSTBOT_LLM_BASE_URL", "https://llm.example.invalid/v1"); monkeypatch.setenv("HOSTBOT_LLM_API_KEY", "test-key"); monkeypatch.setenv("HOSTBOT_LLM_MODEL", "model-x")
    router = build_model_router_from_env(); assert isinstance(router.providers[0], OpenAICompatibleModel); assert router.providers[0].model == "model-x" and router.providers[-1].name == "rule"


def test_api_smoke_and_admin_ui():
    client = TestClient(app); assert client.get("/health").status_code == 200 and "Hostbot Admin" in client.get("/admin").text
    verified = client.post("/v1/stays/verify", json={"property_id": "demo-tokyo", "confirmation_code": "HBDEMO2026"}); assert verified.status_code == 200
    response = client.post("/v1/chat", json={"property_id": "demo-tokyo", "message": "wifi broken", "stay_token": verified.json()["stay_token"]}); assert response.json()["state"] == "wifi_shared"


def test_admin_token_is_enforced_when_configured(monkeypatch):
    monkeypatch.setenv("HOSTBOT_ADMIN_TOKEN", "admin-test"); client = TestClient(app)
    denied = client.get("/v1/admin/demo-org/jobs"); allowed = client.get("/v1/admin/demo-org/jobs", headers={"X-Hostbot-Admin-Token": "admin-test"})
    assert denied.status_code == 401 and allowed.status_code == 200
