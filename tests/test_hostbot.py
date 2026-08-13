import asyncio
from fastapi.testclient import TestClient
from app.core import HostbotService,StayTokens,TokenError,seed_demo
from app.database import PostgresRepository
from app.domain import KnowledgeDocument,Organization,Property
from app.repository import MemoryRepository
from app.main import app

def make():
    r=MemoryRepository();seed_demo(r);return r,HostbotService(r,StayTokens('test-secret'))
def test_flow_and_maintenance_job():
    r,s=make();t=s.verify_stay('demo-tokyo','HBDEMO2026')['stay_token'];a=asyncio.run(s.chat('demo-tokyo','wifi broken',t));b=asyncio.run(s.chat('demo-tokyo','internet still broken',t));c=asyncio.run(s.chat('demo-tokyo','network still broken',t));assert [a['state'],b['state'],c['state']]==['wifi_shared','troubleshooting','ticket_created'];assert len(r.tickets)==1 and len(r.jobs)==1
def test_unverified_denied():
    _,s=make();assert 'verify' in asyncio.run(s.chat('demo-tokyo','wifi broken'))['reply'].lower()
def test_private_scope_and_tenant_rag():
    r,s=make();t=s.verify_stay('demo-tokyo','HBDEMO2026')['stay_token'];assert s.private_property('demo-tokyo',t);r.save_organization(Organization('o2','O2'));r.save_property(Property('p2','o2','P2'));r.save_document(KnowledgeDocument('secret','o2','p2','Secret','ZXQ secret phrase',[]));x=asyncio.run(s.chat('demo-tokyo','ZXQ secret phrase'));assert not any(z['id']=='secret' for z in x['sources'])
def test_token_tamper_rejected():
    m=StayTokens('x');r=MemoryRepository();seed_demo(r);t=m.issue(r.get_reservation('demo-reservation'))
    try:m.verify(t+'x','demo-tokyo');assert False
    except TokenError:pass
def test_sqlalchemy_repository_roundtrip():
    r=PostgresRepository('sqlite+pysqlite:///:memory:');seed_demo(r);assert r.find_reservation('demo-tokyo','HBDEMO2026').id=='demo-reservation'
def test_api_smoke():
    c=TestClient(app);assert c.get('/health').status_code==200;v=c.post('/v1/stays/verify',json={'property_id':'demo-tokyo','confirmation_code':'HBDEMO2026'});assert v.status_code==200;resp=c.post('/v1/chat',json={'property_id':'demo-tokyo','message':'wifi broken','stay_token':v.json()['stay_token']});assert resp.json()['state']=='wifi_shared'
