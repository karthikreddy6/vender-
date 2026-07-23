# OnFood Vendor Server

Separate FastAPI service for the vendor/canteen application. It shares the customer server's PostgreSQL database and existing customer tables.

## Start

```powershell
docker compose up -d
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

The seeded development vendor login is `vendor@onfood.local` / `vendor_password`. Change it before deployment.

Swagger: `http://127.0.0.1:8001/docs`

## Main vendor endpoints

- `POST /api/vendor/auth/login`
- `GET /api/vendor/orders`
- `PATCH /api/vendor/orders/{id}/status`
- `GET /api/vendor/orders/stream`
- `GET|POST /api/vendor/menu`
- `PATCH /api/vendor/menu/{id}`
- `GET|PATCH /api/vendor/kitchen/settings`
- `GET|POST /api/vendor/staff`
