# Node.js Admin Server

This is a small, local-only server that connects directly to the existing PostgreSQL database and provides CRUD APIs for colleges, canteens, categories, menu items, orders, users, vendor accounts, staff, time slots, and kitchen settings.

## Start

```powershell
Copy-Item .env.admin.example .env
npm install
npm start
```

Set `DATABASE_URL` to your PostgreSQL connection string. The server runs only on `http://127.0.0.1:8002` by default and has no API-key authentication.

## Examples

```powershell
Invoke-RestMethod http://127.0.0.1:8002/api/admin/orders
Invoke-RestMethod -Method Patch http://127.0.0.1:8002/api/admin/orders/ORDER_UUID -ContentType 'application/json' -Body '{"status":"PREPARING"}'
Invoke-RestMethod -Method Post http://127.0.0.1:8002/api/admin/canteens -ContentType 'application/json' -Body '{"name":"Main Canteen","is_active":true}'
```

Routes have the form `GET/POST /api/admin/:resource`, `GET/PATCH/DELETE /api/admin/:resource/:id`. Valid resources are available at `GET /api/admin`.

Do not change the bind address or expose this service to the public internet without adding proper authentication.
