# Hostbot v0.2.0

Hostbot is a source-available AI operations platform for hotels, vacation rentals, and other accommodation businesses.

The core rule is that the LLM is **not** the security boundary or workflow authority. Reservation verification, private-data access, tenant isolation, incident transitions, ticket creation, cleaning/maintenance jobs, and administrative actions are enforced by application code.

## Implemented in v0.2.0

- FastAPI guest API and admin API
- Browser-based `/admin` operations dashboard for tickets, cleaning/maintenance jobs, and audit events
- Optional admin API token enforcement with `HOSTBOT_ADMIN_TOKEN`
- Organization -> property -> reservation multi-tenant model
- Signed, short-lived, property-scoped stay tokens
- Public/private property data separation
- Deterministic internet incident state machine
- Automatic support ticket and maintenance-job creation after troubleshooting fails
- Cleaning-job auto-scheduling from imported reservation check-out times
- External reservation de-duplication by organization + channel + external reservation ID
- Audit log for sensitive and operational actions
- PostgreSQL persistence through SQLAlchemy, with in-memory mode for development/tests
- Property-scoped RAG retrieval for house manuals and knowledge documents
- Model router with automatic fallback
- OpenAI-compatible LLM provider wired through environment variables
- Beds24 API v2 connector
- Booking.com Connectivity token authentication and request adapter
- AirHost configurable API adapter for contracted API endpoints
- Airbnb configurable partner adapter for approved API-program endpoints
- LINE Messaging API push connector
- WhatsApp Cloud API text connector
- Normalized single/bulk reservation import API for PMS/channel data

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
uvicorn app.main:app --reload
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Admin dashboard: `http://127.0.0.1:8000/admin`

For PostgreSQL, set `HOSTBOT_REPOSITORY=postgres`, set `DATABASE_URL` to your PostgreSQL SQLAlchemy URL, set a strong `HOSTBOT_TOKEN_SECRET`, then start the API normally.

For a protected admin API, set `HOSTBOT_ADMIN_TOKEN`. The dashboard lets the operator enter this token locally in the browser when loading operational data.

For an OpenAI-compatible LLM endpoint, set `HOSTBOT_LLM_BASE_URL`, `HOSTBOT_LLM_API_KEY`, `HOSTBOT_LLM_MODEL`, and optionally `HOSTBOT_LLM_PROVIDER_NAME`. If the configured model endpoint fails, Hostbot falls back to its deterministic rule provider rather than failing the entire guest workflow.

Demo data:

- property: `demo-tokyo`
- confirmation code: `HBDEMO2026`

Do not use demo credentials or default development secrets in production.

## Reservation and cleaning automation

`POST /v1/admin/reservations` and `POST /v1/admin/reservations/import` normalize PMS/channel reservations into Hostbot. When a reservation includes `check_out`, Hostbot creates one queued cleaning job containing the scheduled check-out time. Re-importing the same `channel + external_id` updates the same local reservation and does not duplicate the cleaning job.

The external provider connector retrieves provider data; the normalization/import layer is deliberately separate because each commercial account can expose different fields, scopes, and enabled APIs.

## External integrations

Beds24 API v2, LINE Messaging API and WhatsApp Cloud API have concrete HTTP clients in `app/connectors.py`.

Booking.com integration requires Connectivity Partner credentials/scopes. Airbnb API access is provided through approved API programs/software partnerships. AirHost API access requires an eligible AirHost ONE plan and API contract. For Airbnb/AirHost, Hostbot intentionally does not invent undocumented endpoints; configure the endpoint path issued to your account.

## Production hardening still recommended

- secret storage in KMS/Vault rather than database JSON
- OIDC/SSO and fine-grained RBAC beyond the current admin-token gate
- encrypted PII fields and retention policies
- background workers/event bus for dispatch, retries, and scheduled execution
- webhook signature validation for each provider
- human approval for refunds, cancellations, payments, and smart-lock actions
- database migrations and backup/restore automation
- LLM evaluation, tracing, cost controls, and prompt/version management

## License and commercial use

**Hostbot is source-available software and is not OSI-approved open source.**

Non-commercial personal, educational, research, and evaluation use is permitted under the repository license.

**Business use, corporate use, production use, SaaS delivery, resale, customer operations, and other commercial use require a paid commercial license agreement with ROOOMTECH株式会社.**

ROOOMTECH株式会社 offers commercial license agreements, implementation, customization, maintenance, and support.

## 日本語

Hostbotは宿泊施設向けAI運用基盤です。予約確認、物件ごとの機密情報制御、RAG、障害対応、チケット、清掃・保守ジョブ、PMS/OTA・メッセージ連携、管理画面を一つの基盤で扱います。

予約取り込み時にチェックアウト時刻があれば清掃ジョブを自動生成し、同一外部予約の再取り込みでは重複を防止します。LLMは環境変数でOpenAI互換APIへ接続でき、障害時はルールベース処理へフォールバックします。

**個人利用、教育、研究、非商用評価は無償です。法人利用、業務利用、本番利用、SaaS提供、再販売を含む商用利用はROOOMTECH株式会社との有償商用ライセンス契約が必要です。**
