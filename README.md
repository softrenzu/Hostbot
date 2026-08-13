# Hostbot

Hostbot is a source-available AI operations foundation for hotels, vacation rentals, and other accommodation businesses.

The core design principle is simple: **AI can interpret a guest request, but server-side code owns authorization and workflow state.**

## v0.1.0 MVP

The current version includes:

- FastAPI guest API
- reservation confirmation flow
- short-lived random stay tokens scoped to a property
- public property information
- verified guest support workflows
- deterministic internet-incident state machine
- support ticket creation after troubleshooting steps
- in-memory audit events
- automated workflow tests

The current MVP intentionally keeps persistence and external integrations simple so the security and workflow model can be reviewed first.

## Architecture

```text
Guest / App
    |
    v
 FastAPI
    |
    +--> Reservation verification
    |        |
    |        +--> short-lived stay token
    |
    +--> HostbotService
             |
             +--> server-side policy
             +--> incident state machine
             +--> support ticket
             +--> audit events
             +--> public property context
```

The LLM is not the final security boundary. Future LLM and RAG layers are intended to sit above the same policy and workflow services rather than directly controlling sensitive operations.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Demo data is included for local evaluation:

- Property ID: `demo-tokyo`
- Confirmation code: `HBDEMO2026`

## Example workflow

1. Call `POST /v1/stays/verify` with the demo property and confirmation code.
2. Send the returned `stay_token` to `POST /v1/chat`.
3. Report an internet problem.
4. The first verified request moves the incident to `wifi_shared`.
5. A second follow-up moves it to `troubleshooting`.
6. A third follow-up creates a support ticket and moves it to `ticket_created`.

The guest cannot skip directly from a new incident to ticket creation because the transition order is enforced in code.

## Tests

```bash
pytest
```

The included tests check that a verified guest reaches ticket creation in the required order and that an unverified guest cannot start the support workflow.

## Planned next modules

- PostgreSQL persistence and tenant isolation
- encrypted property-secret vault integration
- OpenAI-compatible model adapter and model routing
- RAG for house manuals and property documents
- PMS/OTA connectors for Airbnb, Booking.com, Expedia, Beds24, AirHost, Guesty, Hostaway, Cloudbeds and Mews
- LINE, WhatsApp, email and SMS messaging
- operations dashboard and ticket status management
- cleaning assignment and maintenance dispatch
- human approval for higher-risk actions
- revenue and review optimization agents
- event bus for horizontally scaled deployments
- enterprise SSO, RBAC and richer audit trails

## License and commercial use

**Hostbot is source-available software. It is not OSI-approved open source.**

Personal, educational, research and non-commercial evaluation use is permitted under the included `LICENSE`.

**Business use, corporate use and commercial use require a paid commercial license from ROOOMTECH株式会社.** This includes production use by a company, accommodation operations, customer-facing services, paid consulting, resale, SaaS and managed-service use.

ROOOMTECH株式会社 provides separate commercial license agreements as well as implementation, customization, maintenance and support. Contact ROOOMTECH株式会社 before using Hostbot for business.

## 日本語

Hostbotは宿泊施設向けのAI運用基盤です。現在のv0.1.0では、予約確認、短期stay token、宿泊者サポート、インターネット障害の状態管理、チケット生成までを実装しています。

**個人利用、教育、研究、非商用評価は無償です。法人利用、業務利用、商用利用にはROOOMTECH株式会社との有償商用ライセンス契約が必要です。**

ROOOMTECH株式会社では、商用ライセンス契約書、導入支援、カスタマイズ、保守、運用サポートを提供します。ビジネスで利用する場合はROOOMTECH株式会社へお問い合わせください。
