from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .hostbot import HostbotService
from .store import store


app = FastAPI(title="Hostbot", version="0.1.0")
service = HostbotService(store)


class VerifyRequest(BaseModel):
    property_id: str
    confirmation_code: str


class ChatRequest(BaseModel):
    property_id: str
    message: str = Field(min_length=1, max_length=8000)
    stay_token: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "hostbot", "version": "0.1.0"}


@app.post("/v1/stays/verify")
def verify_stay(payload: VerifyRequest):
    result = service.verify_stay(payload.property_id, payload.confirmation_code)
    if not result:
        raise HTTPException(status_code=401, detail="reservation verification failed")
    return result


@app.get("/v1/properties/{property_id}/public")
def public_property(property_id: str):
    result = service.public_property(property_id)
    if result is None:
        raise HTTPException(status_code=404, detail="property not found")
    return {"property_id": property_id, "data": result}


@app.post("/v1/chat")
def chat(payload: ChatRequest):
    result = service.chat(payload.property_id, payload.message, payload.stay_token)
    if result.get("error") == "property not found":
        raise HTTPException(status_code=404, detail="property not found")
    return result
