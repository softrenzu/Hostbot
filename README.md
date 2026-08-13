# Hostbot

Hostbot is a source-available AI operations platform for hotels, vacation rentals, and other accommodation businesses.

It is designed around one rule: **the LLM is not the security boundary and is not the workflow authority**. Sensitive data access, reservation verification, incident transitions, ticket creation, and administrative actions are enforced by server-side policy and state machines.

## What is included

- Guest AI chat API with optional OpenAI-compatible LLM support
- Structured property data first; LLM/RAG can be layered on top
- Reservation confirmation and signed short-lived stay tokens
- Public/private property data separation enforced on the server
- Internet incident state machine enforced in code
- Support ticket lifecycle and admin status updates
- Audit log for security-sensitive actions
- Multi-tenant data model: organization -> property -> reservation
- Connector interfaces for PMS, smart locks, messaging, and maintenance systems
- Docker configuration and automated tests

## Architecture

```text
Guest / OTA / App
      |
      v
   Hostbot API
      |
      +--> Reservation verification --> signed stay token
      |
      +--> Policy engine -------------> allow / deny / approval
      |
      +--> Incident state machine ----> deterministic workflow
      |
      +--> Structured property data --> public / private split
      |
      +--> Optional LLM --------------> wording and public Q&A only
      |
      +--> Tickets / Audit log
      |
      +--> Connectors
            +-- PMS
            +-- Smart lock
            +-- Messaging
            +-- Maintenance
```

## Security model

Hostbot intentionally does **not** rely on prompts such as "never reveal the door code" as the final protection. The private-property endpoint requires a valid stay token and validates that the token belongs to the requested property. Incident transitions are also checked server-side.

By default, private property data is not sent to the LLM. The optional LLM receives public property context only.

## Quick start

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

A demo property and reservation are created automatically for local development:

- Property ID: `demo-tokyo`
- Demo confirmation code: `HBDEMO2026`

The demo credentials are for local evaluation only.

## Example flow

1. Verify a stay:

```bash
curl -X POST http://127.0.0.1:8000/v1/stays/verify \\
  -H 'Content-Type: application/json' \\
  -d '{"property_id":"demo-tokyo","confirmation_code":"HBDEMO2026"}'
```

2. Send the returned `stay_token` to `/v1/chat`.
3. Ask about Wi-Fi. The first internet request returns Wi-Fi credentials, the next returns troubleshooting, and the next creates a support ticket. The order is enforced in code.

## Production roadmap

The current repository is an MVP foundation. Recommended production modules are:

- OTA/PMS connectors for Airbnb, Booking.com, Expedia, Beds24, AirHost, Guesty, Hostaway, Cloudbeds and Mews
- Redis/NATS/Kafka event bus for horizontally scaled real-time workflows
- PostgreSQL row-level tenant isolation
- KMS/Vault-backed encryption for property secrets
- SSO/OIDC and role-based administration
- Human approval queue for high-risk actions such as unlocking doors or issuing refunds
- RAG for house manuals and long-form property documents
- Model routing, evaluation, cost controls and fallback models
- LINE, WhatsApp, email and SMS messaging connectors
- Cleaning assignment, maintenance dispatch, review assistance and revenue optimization

## License and commercial use

**Hostbot is source-available software. It is not OSI-approved open source.**

Non-commercial personal, educational, research, and evaluation use is permitted under the included `LICENSE`.

**Business use and commercial use require a paid commercial license from ROOOMTECH株式会社.** This includes production use by a company, use in paid services, use for customer operations, resale, SaaS delivery, and use on behalf of a commercial organization.

ROOOMTECH株式会社 also offers implementation, maintenance, support, customization, and commercial license agreements. Please contact ROOOMTECH株式会社 if you want to use Hostbot for business.

See `LICENSE` and `COMMERCIAL_LICENSE.md` for details.

## 日本語

Hostbotは宿泊施設向けのAI運用基盤です。AIへの指示だけに依存せず、予約確認、機密情報の参照、インシデント遷移、チケット処理をサーバー側で強制します。

**個人利用、教育、研究、非商用評価は無償です。法人利用、業務利用、商用利用は有償ライセンス契約が必要です。**

ROOOMTECH株式会社では、商用ライセンス契約、導入支援、カスタマイズ、保守、サポートを提供します。ビジネスで利用する場合はROOOMTECH株式会社へご連絡ください。
