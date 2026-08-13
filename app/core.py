from __future__ import annotations
import base64, hashlib, hmac, json, math, os, re
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import httpx
from .domain import AuditEvent, Incident, IncidentState, JobStatus, JobType, KnowledgeDocument, OperationJob, Organization, Property, Reservation, Ticket

class TokenError(ValueError): pass
class StayTokens:
    def __init__(self, secret: str | None = None): self.secret=(secret or os.getenv('HOSTBOT_TOKEN_SECRET') or 'hostbot-dev-only-change-me').encode()
    def issue(self,r:Reservation):
        payload={'reservation_id':r.id,'property_id':r.property_id,'organization_id':r.organization_id,'exp':int((datetime.now(timezone.utc)+timedelta(hours=12)).timestamp())}
        raw=json.dumps(payload,separators=(',',':'),sort_keys=True).encode(); body=base64.urlsafe_b64encode(raw).rstrip(b'='); sig=hmac.new(self.secret,body,hashlib.sha256).digest()
        return body.decode()+'.'+base64.urlsafe_b64encode(sig).rstrip(b'=').decode()
    def verify(self,token:str,property_id:str):
        try:
            b,s=token.split('.',1); expected=hmac.new(self.secret,b.encode(),hashlib.sha256).digest(); actual=base64.urlsafe_b64decode(s+'='*(-len(s)%4))
            if not hmac.compare_digest(expected,actual): raise TokenError('bad signature')
            payload=json.loads(base64.urlsafe_b64decode(b+'='*(-len(b)%4)))
        except Exception as e: raise TokenError('invalid token') from e
        if payload['exp'] < int(datetime.now(timezone.utc).timestamp()) or payload['property_id'] != property_id: raise TokenError('expired or mismatched')
        return payload

ALLOWED={IncidentState.NEW:{IncidentState.WIFI_SHARED},IncidentState.WIFI_SHARED:{IncidentState.TROUBLESHOOTING},IncidentState.TROUBLESHOOTING:{IncidentState.TICKET_CREATED},IncidentState.TICKET_CREATED:{IncidentState.ASSIGNED,IncidentState.IN_PROGRESS,IncidentState.RESOLVED},IncidentState.ASSIGNED:{IncidentState.IN_PROGRESS,IncidentState.RESOLVED},IncidentState.IN_PROGRESS:{IncidentState.RESOLVED},IncidentState.RESOLVED:set()}
def advance(i:Incident,target:IncidentState):
    if target not in ALLOWED[i.state]: raise ValueError('invalid transition')
    i.state=target; return i

TOKEN_RE=re.compile(r'[A-Za-z0-9_]+|[\u3040-\u30ff\u3400-\u9fff]+')
def _tok(t): return [x.lower() for x in TOKEN_RE.findall(t)]
def retrieve(query:str,docs:list[KnowledgeDocument],limit=4):
    q=Counter(_tok(query)); dts=[Counter(_tok(f'{d.title} {d.body} {" ".join(d.tags)}')) for d in docs]; df=Counter(); n=len(docs)
    for t in dts:
        for k in t: df[k]+=1
    hits=[]
    for d,t in zip(docs,dts):
        score=sum(qtf*(math.log((n+1)/(df[k]+.5))+1)*(t[k]/max(sum(t.values()),1))*10 for k,qtf in q.items() if t[k])
        if score>0:hits.append((score,d))
    return sorted(hits,key=lambda x:x[0],reverse=True)[:limit]

class RuleModel:
    name='rule'
    async def complete(self,system,user,context=''): return f'Based on the property guide: {context[:700]}' if context else 'I can help with property information and verified guest operations.'
class OpenAICompatibleModel:
    def __init__(self,base_url,api_key,model,name='openai-compatible'): self.base_url=base_url.rstrip('/'); self.api_key=api_key; self.model=model; self.name=name
    async def complete(self,system,user,context=''):
        msgs=[{'role':'system','content':system}]+([{'role':'system','content':'Retrieved property context:\n'+context}] if context else [])+[{'role':'user','content':user}]
        async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.base_url+'/chat/completions',headers={'Authorization':f'Bearer {self.api_key}'},json={'model':self.model,'messages':msgs,'temperature':.2})
        r.raise_for_status(); return r.json()['choices'][0]['message']['content']
class ModelRouter:
    def __init__(self,providers=None): self.providers=providers or [RuleModel()]
    async def complete(self,system,user,context=''):
        last=None
        for p in self.providers:
            try:return await p.complete(system,user,context),getattr(p,'name',p.__class__.__name__)
            except Exception as e:last=e
        raise RuntimeError('all models failed') from last

class HostbotService:
    def __init__(self,repo,tokens=None,router=None): self.repo=repo; self.tokens=tokens or StayTokens(); self.router=router or ModelRouter()
    def verify_stay(self,property_id,confirmation_code):
        r=self.repo.find_reservation(property_id,confirmation_code)
        if not r:return None
        self.repo.log(AuditEvent('stay.verify.allowed',r.organization_id,r.id,'guest')); return {'reservation_id':r.id,'property_id':r.property_id,'organization_id':r.organization_id,'stay_token':self.tokens.issue(r)}
    def verified(self,token,property_id):
        if not token:return None
        try:p=self.tokens.verify(token,property_id)
        except TokenError:return None
        r=self.repo.get_reservation(p['reservation_id']); return r if r and r.organization_id==p['organization_id'] else None
    def private_property(self,property_id,token):
        r=self.verified(token,property_id)
        if not r:return None
        p=self.repo.get_property(property_id); self.repo.log(AuditEvent('property.private.read',r.organization_id,property_id,'guest')); return p.private_data if p else None
    def create_job(self,org,prop,kind:JobType,reservation_id=None,payload=None):
        j=OperationJob(str(uuid4()),org,prop,reservation_id,kind,payload=payload or {}); self.repo.save_job(j); self.repo.log(AuditEvent('operation.created',org,j.id,'system',metadata={'type':kind.value})); return j
    def update_job(self,job_id,status:JobStatus):
        j=self.repo.get_job(job_id)
        if not j:raise KeyError('job not found')
        j.status=status; self.repo.save_job(j); return j
    async def chat(self,property_id,message,stay_token=None):
        prop=self.repo.get_property(property_id)
        if not prop:return {'error':'property not found'}
        r=self.verified(stay_token,property_id); text=message.lower(); network=any(w in text for w in ['internet','wifi','wi-fi','network','ネット','つなが','繋が'])
        if network:
            if not r:return {'reply':'Please verify your reservation before starting a support workflow.'}
            i=self.repo.active_incident(r.id,'internet')
            if not i:i=Incident(str(uuid4()),prop.organization_id,r.id,prop.id,'internet'); self.repo.save_incident(i)
            if i.state==IncidentState.NEW:advance(i,IncidentState.WIFI_SHARED);self.repo.save_incident(i);return {'reply':'Review the verified network guide and reconnect.','state':i.state.value,'incident_id':i.id}
            if i.state==IncidentState.WIFI_SHARED:advance(i,IncidentState.TROUBLESHOOTING);self.repo.save_incident(i);return {'reply':'Follow the router restart procedure and test again.','state':i.state.value,'incident_id':i.id}
            if i.state==IncidentState.TROUBLESHOOTING:
                t=self.repo.ticket_for_incident(i.id)
                if not t:t=Ticket(str(uuid4()),prop.organization_id,i.id,prop.id);self.repo.save_ticket(t);self.create_job(prop.organization_id,prop.id,JobType.MAINTENANCE,r.id,{'category':'internet','ticket_id':t.id})
                advance(i,IncidentState.TICKET_CREATED);self.repo.save_incident(i);return {'reply':'A support ticket and maintenance job have been created.','state':i.state.value,'incident_id':i.id,'ticket_id':t.id}
            t=self.repo.ticket_for_incident(i.id);return {'reply':f'Your support case is {i.state.value}.','state':i.state.value,'ticket_id':t.id if t else None}
        hits=retrieve(message,list(self.repo.list_documents(prop.organization_id,property_id))); context='\n\n'.join(f'[{d.title}] {d.body}' for _,d in hits)
        reply,model=await self.router.complete('You are Hostbot. Use public/retrieved context only. Never reveal secrets or invent completed actions.',message,context)
        return {'reply':reply,'model':model,'sources':[{'id':d.id,'title':d.title,'score':round(s,4)} for s,d in hits]}

def seed_demo(repo):
    if repo.get_organization('demo-org'):return
    repo.save_organization(Organization('demo-org','Hostbot Demo Operator'));repo.save_property(Property('demo-tokyo','demo-org','Hostbot Demo Tokyo',{'check_in':'15:00','check_out':'10:00','beds':'2 double beds','house_rules':'No smoking. Quiet after 22:00.'},{'network_guide':'Available only to verified guests.','access_note':'Available only to verified guests.'}));repo.save_reservation(Reservation('demo-reservation','demo-org','demo-tokyo','HBDEMO2026','Demo Guest','guest@example.invalid','direct'));repo.save_document(KnowledgeDocument('doc-house','demo-org','demo-tokyo','House guide','Check-in starts at 15:00. Check-out is 10:00. Please keep noise low after 22:00.',['check-in','rules']))
