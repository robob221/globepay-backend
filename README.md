# GlobePay

GlobePay is a Ghana-first personal finance platform for wallet payments, savings vaults, split bills, cards, and cross-border transfers. This repository contains the FastAPI backend and a React + CRACO dashboard UI.

## Project structure

```text
GlobePay/
├── frontend/       # React 18 dashboard, built with CRACO
├── src/            # FastAPI application and domain modules
├── migrations/     # Alembic database migrations
├── requirements.txt
└── .env.example
```

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm 9+
- PostgreSQL 14+
- Paystack and optional Bitnob/SMS sandbox credentials for payment features

## Backend setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/susu_platform
JWT_SECRET_KEY=replace-this-with-a-long-random-value
```

Create the PostgreSQL database, then apply migrations:

```bash
createdb susu_platform
alembic upgrade head
```

Start the API in development mode:

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Useful URLs:

- API health check: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

The API uses bearer tokens. Authenticate with `POST /auth/register` and `POST /auth/login`, then send the returned token as `Authorization: Bearer <token>`.

## Frontend setup

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env.local
npm start
```

The dashboard opens at http://localhost:3000. The default API URL is `http://localhost:8000` and can be changed in `frontend/.env.local`:

```env
REACT_APP_API_URL=http://localhost:8000
```

The dashboard is integrated with the FastAPI backend. It authenticates with `/auth/login` and `/auth/register`, stores the bearer token locally, loads the current user, reads wallet summary and transfer history, and reads the user's vaults. The dashboard includes loading, API error, refresh, logout, and empty states. The displayed wallet net flow is derived from completed wallet transfers because the backend intentionally does not store a custodial wallet balance.

The live dashboard uses these backend calls:

```text
POST /auth/login
POST /auth/register
GET  /auth/me
GET  /wallet/summary
GET  /wallet/transfers
GET  /vaults
```

The backend now exposes `GET /wallet/summary`, which aggregates completed transfer history into received total, sent total, fees, round-ups, and net flow. CORS is enabled for the local React development origins `http://localhost:3000` and `http://127.0.0.1:3000`.

The dashboard also includes authenticated mutation forms for:

```text
POST /wallet/transfers     # Send money; uses an Idempotency-Key
POST /vaults                # Create a savings vault
GET  /cards                 # Load the user's virtual cards
POST /cards                 # Start virtual-card creation; uses an Idempotency-Key
POST /cards/{card_id}/fund  # Available through the API client for card funding
POST /cards/{card_id}/freeze
POST /cards/{card_id}/unfreeze
POST /vaults/{vault_id}/contribute
POST /vaults/{vault_id}/withdraw
GET  /crossborder/transfers
POST /crossborder/transfers
```

The Cards panel now exposes **Fund**, **Freeze**, and **Unfreeze** controls for each returned card. Send-money, card-creation, and card-funding requests return the backend's Paystack authorization reference. These provider-backed actions require valid Paystack sandbox configuration in `.env`; vault creation and card status changes work directly against the configured database.

Each live vault card now exposes **Contribute** and **Withdraw** actions. Contributions use an idempotency key and return the Paystack authorization reference; withdrawals collect the mobile-money destination and call the backend withdrawal endpoint.

The dashboard also loads cross-border transfer history and exposes a **Go global** form from the Transfers navigation and dashboard panel. It collects the source GHS amount, destination country and currency, beneficiary details, mobile-money network, and sender email, then calls `POST /crossborder/transfers` with an idempotency key. The sandbox Bitnob and Paystack credentials must be configured before using provider-backed transfers.

The group/susu and trust-scoring backend features have been removed from this version. The remaining backend modules cover authentication, wallet transfers, vaults, cards, payments, cross-border transfers, and split bills.

## Production builds

Build the frontend:

```bash
cd frontend
npm run build
```

Serve the generated `frontend/build` directory with a static server or reverse proxy. Run the backend with a production process manager, for example:

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
```

For production, use a strong `JWT_SECRET_KEY`, a managed PostgreSQL database, HTTPS, restricted CORS/reverse-proxy rules, and real payment-provider webhook secrets. Never commit `.env` or payment credentials.

## Testing and development commands

```bash
# Backend tests (when test files are present)
pytest

# Frontend checks/build
cd frontend
npm test
npm run build
```

## Notes

- Payment and cross-border actions depend on provider credentials and should be exercised in sandbox/test mode first.
- Run `alembic upgrade head` whenever the migration history changes.
- The frontend uses a responsive layout and is optimized for desktop dashboard widths while remaining usable on mobile screens.
