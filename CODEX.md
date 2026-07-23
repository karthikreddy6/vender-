# OnFood Vendor Server Walkthrough

## Purpose

This repository contains the separate vendor/canteen backend for OnFood. The customer backend remains in the sibling `onfoodserver` project. Both services use the same PostgreSQL database.

```text
Customer Android app
        |
        v
Customer server :8000 ------ PostgreSQL database
                                  ^
                                  |
Vendor Android app ---- Vendor server :8001
```

The vendor server reads the customer-created orders from PostgreSQL and lets kitchen staff manage the order queue, menu, stock, kitchen settings, and staff records.

## Technology

- FastAPI
- Python async SQLAlchemy
- PostgreSQL with `asyncpg`
- Alembic migrations
- JWT bearer authentication
- Server-Sent Events for vendor order updates
- Uvicorn

## Directory Structure

```text
app/
  main.py                 FastAPI application and startup seed
  config.py               Environment configuration
  database.py             Async PostgreSQL engine and session
  models.py               Shared customer models plus vendor models
  security.py             Password hashing, JWT creation, vendor auth
  exceptions.py           API error response handlers
  sse.py                  SSE connection manager
  vendor_schemas.py       Vendor request validation models
  routers/
    vendor_auth.py        Vendor login and current-account endpoint
    vendor.py             Orders, menu, kitchen, staff, and SSE routes
migrations/
  env.py                  Alembic model registration
  versions/                Shared migration history plus vendor migration
VENDOR_API_AND_COMMUNICATION.md
  Full API and Android communication reference
CODEX.md
  This architecture and maintenance guide
```

## Startup Flow

1. Uvicorn loads `app.main:app`.
2. The FastAPI lifespan function connects to PostgreSQL.
3. It creates the default kitchen settings row if missing.
4. It creates the development vendor account if missing.
5. FastAPI registers vendor authentication and management routes.
6. The server listens on port `8001`.

The development account is:

```text
Email: vendor@onfood.local
Password: vendor_password
```

Change this before production use.

## Authentication Flow

The vendor app calls:

```http
POST /api/vendor/auth/login
```

The server verifies the bcrypt password and returns a JWT containing:

```json
{
  "sub": "vendor-account-id",
  "role": "admin",
  "iss": "onfood",
  "exp": "expiration-time"
}
```

The Android app stores the access token and sends it on protected requests:

```http
Authorization: Bearer JWT_TOKEN
```

Only tokens with `staff` or `admin` roles are accepted by vendor routes.

## Order Data Flow

1. A customer places an order through the existing customer server.
2. The customer server saves an `orders` row and related `order_items` rows in PostgreSQL.
3. The vendor app calls `GET /api/vendor/orders`.
4. The vendor server loads active orders and their menu items from PostgreSQL.
5. The response is converted into the field names expected by the Android vendor app.
6. The vendor app stores the remote order in its local Room database.
7. Staff changes the status through:

```http
PATCH /api/vendor/orders/{orderId}/status
```

8. The vendor server updates PostgreSQL and broadcasts an SSE event.
9. The Android sync process updates its local Room order.

Order status flow:

```text
PLACED -> PREPARING -> READY_FOR_PICKUP -> DELIVERED
```

Scheduled orders use `SCHEDULED` until preparation begins.

## Vendor API Groups

```text
POST  /api/vendor/auth/login
GET   /api/vendor/auth/me

GET   /api/vendor/orders
PATCH /api/vendor/orders/{id}/status
GET   /api/vendor/orders/stream

GET   /api/vendor/menu
POST  /api/vendor/menu
PATCH /api/vendor/menu/{id}

GET   /api/vendor/kitchen/settings
PATCH /api/vendor/kitchen/settings

GET   /api/vendor/staff
POST  /api/vendor/staff
```

Full request and response examples are in `VENDOR_API_AND_COMMUNICATION.md`.

## Real-Time Communication

The vendor Android app opens:

```http
GET /api/vendor/orders/stream
Accept: text/event-stream
```

The server sends:

```text
event: connected
data: ok
```

When an order status changes:

```text
event: order-status
data: { ...order JSON... }
```

The app also polls `GET /api/vendor/orders` before opening SSE and after reconnecting. This prevents missed orders during a temporary network failure.

## Shared Database

The vendor server uses the same connection string as the customer server:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/onfood
```

The original customer tables remain shared:

- `users`
- `categories`
- `menu_items`
- `cart_items`
- `orders`
- `order_items`
- `time_slots`
- `kitchen_settings`

Vendor-specific additions are:

- `vendor_accounts`
- `staff_members`
- `menu_items.description`
- `menu_items.stock`
- `menu_items.is_student_visible`

Apply the vendor migration with:

```powershell
alembic upgrade head
```

The migration is `9b4e7f2a1c11_add_vendor_support.py` and continues the existing customer migration chain.

## Android Connection Addresses

```text
Android emulator:       http://10.0.2.2:8001/
Physical phone on Wi-Fi: http://COMPUTER_LAN_IP:8001/
Browser on computer:     http://127.0.0.1:8001/
```

The Android app must have:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

The vendor Android project uses Retrofit and OkHttp in `NetworkClient.kt`. It saves the server address and JWT in its local Room preferences and synchronizes remote data through `CanteenRepository.kt`.

## Changes Made

### Server implementation

- Created the vendor FastAPI service in this repository.
- Reused the existing customer server's database model and Alembic migration history.
- Added `VendorAccount` and `StaffMember` models.
- Added vendor JWT login and role validation.
- Added order queue and status update APIs.
- Added vendor SSE order stream.
- Added menu creation, menu updates, stock, visibility, and availability controls.
- Added kitchen settings APIs.
- Added staff listing and creation APIs.
- Added default kitchen settings and development vendor seed data.

### Database migration

- Added `vendor_accounts`.
- Added `staff_members`.
- Added inventory and description columns to `menu_items`.
- Applied the migration to the shared PostgreSQL database.

### Android compatibility fix

The Android vendor models expected fields such as `token`, `student_name`, `items_summary`, and numeric prices. The first server response used different names and string numeric values. The vendor response mapper was updated to provide the Android-compatible fields and numeric values. Orders are also returned newest first.

### Documentation

- Added `VENDOR_API_AND_COMMUNICATION.md` with the endpoint reference.
- Added this `CODEX.md` walkthrough.

## Running Locally

From this directory:

```powershell
Copy-Item .env.example .env
..\onfoodserver\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Open:

```text
http://127.0.0.1:8001/docs
```

## Troubleshooting

### Order exists in PostgreSQL but not in Android

Check these items in order:

1. Confirm the vendor server is listening on port `8001`.
2. Open `http://127.0.0.1:8001/docs` from the server computer.
3. Use `10.0.2.2:8001` for an Android emulator, not `127.0.0.1:8001`.
4. Use the computer's LAN IP for a physical phone.
5. Log in again so the app receives a current JWT.
6. Confirm `GET /api/vendor/orders` returns the order.
7. Rebuild the Android app after networking or model changes.
8. Check Android Logcat for Retrofit, HTTP, or JSON parsing errors.

### `vendor_accounts` table is missing

Run:

```powershell
alembic upgrade head
```

### Authentication fails

Confirm the vendor account exists and use the exact development credentials listed above. Also confirm the Android app is using the vendor server URL with port `8001`.

## Important Boundaries

- Do not add customer checkout logic to this vendor service.
- Do not use a second PostgreSQL database for the vendor app.
- Do not expose the development vendor password in production.
- Do not store JWT tokens in plain text in a production Android build.
- Any schema change must be added as a new Alembic migration.
