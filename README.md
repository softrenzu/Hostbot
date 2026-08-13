# Hostbot v0.2.0

Hostbot is a source-available AI operations platform for hotels, vacation rentals, and other accommodation businesses.

The core design rule is that the LLM is **not** the security boundary or workflow authority. Reservation verification, private-data access, tenant isolation, incident transitions, tickets, cleaning jobs, and maintenance jobs are enforced by application code.

## Implemented in v0.2.0

- FastAPI guest and admin API
- Organization -> property -> reservation multi-tenant model
- Signed, short-lived, property-scoped stay tokens
- Public/private property data separation
- Deterministic internet incident state machine
- Support tickets plus automatic maintenance-job creation
- Cleaning and maintenance job model/status API
- Audit log
- PostgreSQL persistence through SQLAlchemy, with in-memory mode for development/tests
- RAG retrieval for house manuals and property knowledge
- Model router with fallback providers and OpenAI-compatible HTTP provider
- Beds24 API v2 connector
- Booking.com Connectivity token authentication and request adapter
- AirHost configurable API adapter for contracted API endpoints
- Airbnb configurable partner adapter for approved API-program endpoints
- LINE Messaging API push connector
- WhatsApp Cloud API text connector

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

For PostgreSQL, set `HOSTBOT_REPOSITORY=postgres`, set `DATABASE_URL` to your PostgreSQL SQLAlchemy URL, set a strong `HOSTBOT_TOKEN_SECRET`, then start the API normally.

Demo data:

- property: `demo-tokyo`
- confirmation code: `HBDEMO2026`

Do not use demo credentials in production.

## External integrations

Beds24 API v2, LINE Messaging API and WhatsApp Cloud API have concrete HTTP clients in `app/connectors.py`.

Booking.com integration requires Connectivity Partner credentials/scopes. Airbnb API access is provided through approved API programs/software partnerships. AirHost API access requires an eligible AirHost ONE plan and API contract. For Airbnb/AirHost, Hostbot intentionally does not invent undocumented endpoints; configure the endpoint path issued to your account.

## Production hardening still recommended

- secret storage in KMS/Vault rather than database JSON
- SSO/OIDC and RBAC for the admin API
- encrypted PII fields and retention policies
- background workers/event bus for dispatch and retries
- webhook signature validation for each provider
- human approval UI for refunds, cancellations, and smart-lock actions
- database migrations and backup/restore automation
- evaluation/observability for LLM responses

## License and commercial use

**Hostbot is source-available software and is not OSI-approved open source.**

Non-commercial personal, educational, research, and evaluation use is permitted under the repository license.

**Business use, corporate use, production use, SaaS delivery, resale, customer operations, and other commercial use require a paid commercial license agreement with ROOOMTECH株式会社.**

ROOOMTECH株式会社 offers commercial license agreements, implementation, customization, maintenance, and support.

## 日本語

Hostbotは宿泊施設向けAI運用基盤です。予約確認、物件ごとの機密情報制御、RAG、障害対応、チケット、清掃・保守ジョブ、外部PMS・メッセージ連携を一つの基盤で扱います。

**個人利用、教育、研究、非商用評価は無償です。法人利用、業務利用、本番利用、SaaS提供、再販売を含む商用利用はROOOMTECH株式会社との有償商用ライセンス契約が必要です。**
