from __future__ import annotations

import os
from dataclasses import asdict
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .core import HostbotService, build_model_router_from_env, seed_demo
from .database import PostgresRepository
from .domain import JobStatus, JobType, KnowledgeDocument, Organization, Property, Reservation
from .repository import MemoryRepository


def build_repository():
    if os.getenv("HOSTBOT_REPOSITORY", "memory").lower() == "postgres":
        return PostgresRepository()
    return MemoryRepository()


def require_admin(x_hostbot_admin_token: str | None = Header(default=None)):
    configured = os.getenv("HOSTBOT_ADMIN_TOKEN")
    if configured and x_hostbot_admin_token != configured:
        raise HTTPException(401, "invalid admin token")
    return True


repo = build_repository()
seed_demo(repo)
service = HostbotService(repo, router=build_model_router_from_env())
app = FastAPI(title="Hostbot", version="0.2.0")


class StayRequest(BaseModel):
    property_id: str
    confirmation_code: str


class ChatRequest(BaseModel):
    property_id: str
    message: str
    stay_token: str | None = None


class OrganizationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str


class PropertyRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    name: str
    public_data: dict = Field(default_factory=dict)
    private_data: dict = Field(default_factory=dict)


class ReservationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    property_id: str
    confirmation_code: str
    guest_name: str = ""
    guest_contact: str = ""
    channel: str = "direct"
    external_id: str | None = None
    check_in: str | None = None
    check_out: str | None = None


class ReservationImportRequest(BaseModel):
    reservations: list[ReservationRequest]
    schedule_cleaning: bool = True


class KnowledgeRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    property_id: str | None = None
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)


class JobRequest(BaseModel):
    organization_id: str
    property_id: str
    reservation_id: str | None = None
    type: JobType
    payload: dict = Field(default_factory=dict)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0", "repository": repo.__class__.__name__, "model_router": [getattr(provider, "name", provider.__class__.__name__) for provider in service.router.providers]}


@app.post("/v1/stays/verify")
def verify_stay(request: StayRequest):
    result = service.verify_stay(request.property_id, request.confirmation_code)
    if not result:
        raise HTTPException(401, "invalid stay")
    return result


@app.get("/v1/properties/{property_id}/public")
def public_property(property_id: str):
    property_obj = repo.get_property(property_id)
    if not property_obj:
        raise HTTPException(404, "property not found")
    return property_obj.public_data


@app.get("/v1/properties/{property_id}/private")
def private_property(property_id: str, authorization: str | None = Header(default=None)):
    token = (authorization or "").removeprefix("Bearer ").strip()
    data = service.private_property(property_id, token)
    if data is None:
        raise HTTPException(403, "verified stay required")
    return data


@app.post("/v1/chat")
async def chat(request: ChatRequest):
    return await service.chat(request.property_id, request.message, request.stay_token)


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return ADMIN_HTML


@app.post("/v1/admin/organizations", dependencies=[Depends(require_admin)])
def add_organization(request: OrganizationRequest):
    return asdict(repo.save_organization(Organization(request.id, request.name)))


@app.post("/v1/admin/properties", dependencies=[Depends(require_admin)])
def add_property(request: PropertyRequest):
    return asdict(repo.save_property(Property(request.id, request.organization_id, request.name, request.public_data, request.private_data)))


@app.post("/v1/admin/reservations", dependencies=[Depends(require_admin)])
def add_reservation(request: ReservationRequest):
    reservation, cleaning = service.ingest_reservation(Reservation(**request.model_dump()))
    return {"reservation": asdict(reservation), "cleaning_job": asdict(cleaning) if cleaning else None}


@app.post("/v1/admin/reservations/import", dependencies=[Depends(require_admin)])
def import_reservations(request: ReservationImportRequest):
    results = []
    for item in request.reservations:
        reservation, cleaning = service.ingest_reservation(Reservation(**item.model_dump()), schedule_cleaning=request.schedule_cleaning)
        results.append({"reservation": asdict(reservation), "cleaning_job": asdict(cleaning) if cleaning else None})
    return {"imported": len(results), "items": results}


@app.post("/v1/admin/reservations/{reservation_id}/schedule-cleaning", dependencies=[Depends(require_admin)])
def schedule_cleaning(reservation_id: str):
    reservation = repo.get_reservation(reservation_id)
    if not reservation:
        raise HTTPException(404, "reservation not found")
    job = service.create_job(reservation.organization_id, reservation.property_id, JobType.CLEANING, reservation.id, {"scheduled_for": reservation.check_out, "source": reservation.channel})
    return asdict(job)


@app.post("/v1/admin/knowledge", dependencies=[Depends(require_admin)])
def add_knowledge(request: KnowledgeRequest):
    return asdict(repo.save_document(KnowledgeDocument(**request.model_dump())))


@app.post("/v1/admin/jobs", dependencies=[Depends(require_admin)])
def add_job(request: JobRequest):
    return asdict(service.create_job(request.organization_id, request.property_id, request.type, request.reservation_id, request.payload))


@app.patch("/v1/admin/jobs/{job_id}/{status}", dependencies=[Depends(require_admin)])
def update_job(job_id: str, status: JobStatus):
    try:
        return asdict(service.update_job(job_id, status))
    except KeyError as exc:
        raise HTTPException(404, "job not found") from exc


@app.get("/v1/admin/{organization_id}/tickets", dependencies=[Depends(require_admin)])
def list_tickets(organization_id: str):
    return [asdict(item) for item in repo.list_tickets(organization_id)]


@app.get("/v1/admin/{organization_id}/jobs", dependencies=[Depends(require_admin)])
def list_jobs(organization_id: str):
    return [asdict(item) for item in repo.list_jobs(organization_id)]


@app.get("/v1/admin/{organization_id}/audit", dependencies=[Depends(require_admin)])
def list_audit(organization_id: str):
    return [asdict(item) for item in repo.list_audit(organization_id)]


ADMIN_HTML = r"""
<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Hostbot Admin</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#17202a}header{background:#111827;color:white;padding:18px 24px}main{padding:24px;max-width:1200px;margin:auto}.controls,.cards{display:flex;gap:12px;flex-wrap:wrap}.controls{margin-bottom:20px}input,button{padding:10px 12px;border:1px solid #cbd5e1;border-radius:8px}button{background:#111827;color:white;cursor:pointer}.card{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px;flex:1;min-width:280px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px;border-bottom:1px solid #e2e8f0;vertical-align:top}.muted{color:#64748b;font-size:12px}.error{color:#b91c1c}</style></head>
<body><header><strong>Hostbot Admin</strong> <span class="muted">v0.2.0</span></header><main><div class="controls"><input id="org" value="demo-org" placeholder="Organization ID"><input id="token" type="password" placeholder="Admin token if configured"><button onclick="loadAll()">更新</button></div><div id="message" class="error"></div><div class="cards"><section class="card"><h3>Tickets</h3><div id="tickets"></div></section><section class="card"><h3>Cleaning / Maintenance</h3><div id="jobs"></div></section><section class="card"><h3>Audit</h3><div id="audit"></div></section></div></main>
<script>const headers=()=>{const t=document.getElementById('token').value;return t?{'X-Hostbot-Admin-Token':t}:{}};const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function table(rows,cols){if(!rows.length)return '<p class="muted">No data</p>';return '<table><thead><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+esc(typeof r[c]==='object'?JSON.stringify(r[c]):r[c])+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}async function get(path){const r=await fetch(path,{headers:headers()});if(!r.ok)throw new Error(await r.text());return r.json()}async function loadAll(){document.getElementById('message').textContent='';const org=encodeURIComponent(document.getElementById('org').value);try{const[t,j,a]=await Promise.all([get('/v1/admin/'+org+'/tickets'),get('/v1/admin/'+org+'/jobs'),get('/v1/admin/'+org+'/audit')]);document.getElementById('tickets').innerHTML=table(t,['id','property_id','status','assignee']);document.getElementById('jobs').innerHTML=table(j,['id','type','status','property_id','reservation_id','payload']);document.getElementById('audit').innerHTML=table(a.slice(-50).reverse(),['created_at','action','resource_id','actor'])}catch(e){document.getElementById('message').textContent=e.message}}loadAll();</script></body></html>
"""
