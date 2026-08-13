from __future__ import annotations
from dataclasses import dataclass
import httpx
@dataclass
class Result: ok:bool; provider:str; data:object=None; error:str|None=None
class Beds24Connector:
    def __init__(self,token,base_url='https://beds24.com/api/v2'):self.token=token;self.base_url=base_url.rstrip('/')
    async def reservations(self,**filters):
        async with httpx.AsyncClient(timeout=30) as c:r=await c.get(self.base_url+'/bookings',headers={'token':self.token},params=filters)
        return Result(r.is_success,'beds24',r.json() if r.is_success and r.content else None,None if r.is_success else r.text[:300])
    async def send_booking_message(self,payload):
        async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.base_url+'/bookings/messages',headers={'token':self.token},json=payload)
        return Result(r.is_success,'beds24',r.json() if r.is_success and r.content else None,None if r.is_success else r.text[:300])
class BookingConnector:
    AUTH='https://connectivity-authentication.booking.com/token-based-authentication/exchange'
    def __init__(self,client_id,client_secret,supply_base='https://supply-xml.booking.com'):self.client_id=client_id;self.client_secret=client_secret;self.supply_base=supply_base.rstrip('/');self.token=None
    async def authenticate(self):
        async with httpx.AsyncClient(timeout=30) as c:r=await c.post(self.AUTH,json={'client_id':self.client_id,'client_secret':self.client_secret})
        r.raise_for_status();d=r.json();self.token=d.get('access_token') or d.get('token');return self.token
    async def request(self,method,path,**kwargs):
        token=self.token or await self.authenticate();h={'Authorization':f'Bearer {token}'};h.update(kwargs.pop('headers',{}))
        async with httpx.AsyncClient(timeout=30) as c:r=await c.request(method,self.supply_base+'/'+path.lstrip('/'),headers=h,**kwargs)
        return Result(r.is_success,'booking.com',r.json() if r.content and 'json' in r.headers.get('content-type','') else r.text,None if r.is_success else f'HTTP {r.status_code}')
class PartnerConnector:
    def __init__(self,provider,base_url,token,reservation_path):self.provider=provider;self.base_url=base_url.rstrip('/');self.token=token;self.path=reservation_path
    async def reservations(self,**filters):
        async with httpx.AsyncClient(timeout=30) as c:r=await c.get(self.base_url+'/'+self.path.lstrip('/'),headers={'Authorization':f'Bearer {self.token}'},params=filters)
        return Result(r.is_success,self.provider,r.json() if r.content and 'json' in r.headers.get('content-type','') else r.text,None if r.is_success else f'HTTP {r.status_code}')
class AirHostConnector(PartnerConnector):
    def __init__(self,base_url,token,reservation_path):super().__init__('airhost',base_url,token,reservation_path)
class AirbnbConnector(PartnerConnector):
    def __init__(self,base_url,token,reservation_path):super().__init__('airbnb',base_url,token,reservation_path)
class LineConnector:
    URL='https://api.line.me/v2/bot/message/push'
    def __init__(self,token):self.token=token
    async def send_text(self,to,text):
        async with httpx.AsyncClient(timeout=20) as c:r=await c.post(self.URL,headers={'Authorization':f'Bearer {self.token}'},json={'to':to,'messages':[{'type':'text','text':text}]})
        return Result(r.is_success,'line',r.json() if r.is_success and r.content else None,None if r.is_success else r.text[:300])
class WhatsAppConnector:
    def __init__(self,token,phone_number_id,graph_version='v23.0'):self.token=token;self.phone=phone_number_id;self.version=graph_version
    async def send_text(self,to,text):
        url=f'https://graph.facebook.com/{self.version}/{self.phone}/messages';payload={'messaging_product':'whatsapp','recipient_type':'individual','to':to,'type':'text','text':{'preview_url':False,'body':text}}
        async with httpx.AsyncClient(timeout=20) as c:r=await c.post(url,headers={'Authorization':f'Bearer {self.token}'},json=payload)
        return Result(r.is_success,'whatsapp',r.json() if r.is_success and r.content else None,None if r.is_success else r.text[:300])
