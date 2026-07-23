# OnFood Vendor API and Communication Guide

This document describes how the vendor Android app communicates with the vendor server. The vendor server uses the same PostgreSQL database as the customer server.

## Server URLs

| Client location | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8001` |
| Android device on same Wi-Fi | `http://YOUR_COMPUTER_IP:8001` |
| Local browser | `http://127.0.0.1:8001` |

The Android app must include this permission:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

## Authentication

### Login

```http
POST /api/vendor/auth/login
Content-Type: application/json
```

```json
{
  "email": "vendor@onfood.local",
  "password": "vendor_password"
}
```

Response:

```json
{
  "access_token": "JWT_TOKEN",
  "token_type": "bearer",
  "vendor": {
    "id": "vendor-id",
    "name": "OnFood Vendor",
    "email": "vendor@onfood.local",
    "role": "admin",
    "canteenId": "canteen-uuid"
  }
}
```

Save `access_token` securely. Also store `vendor.canteenId` for UI display. Send the token with every protected request:

```http
Authorization: Bearer JWT_TOKEN
```

### Current vendor

```http
GET /api/vendor/auth/me
Authorization: Bearer JWT_TOKEN
```

The vendor app does not send `canteenId` in order, menu, or staff requests. The server reads the vendor canteen from the JWT and automatically scopes access to that canteen.

## Order APIs

### Get active order queue

```http
GET /api/vendor/orders
Authorization: Bearer JWT_TOKEN
```

This returns only orders for the logged-in vendor's canteen.

Optional status filter:

```http
GET /api/vendor/orders?status=PLACED&status=PREPARING
```

Order statuses:

```text
PLACED, SCHEDULED, PREPARING, READY_FOR_PICKUP, DELIVERED
```

### Update order status

```http
PATCH /api/vendor/orders/{orderId}/status
Authorization: Bearer JWT_TOKEN
Content-Type: application/json
```

```json
{
  "status": "PREPARING"
}
```

Typical flow:

```text
PLACED -> PREPARING -> READY_FOR_PICKUP -> DELIVERED
```

*Note: Transitioning an order to `DELIVERED` automatically decreases the `stock` quantity for each ordered menu item in the database (ensuring stock does not drop below 0).*

## Real-time order updates

Open one long-running SSE connection after vendor login:

```http
GET /api/vendor/orders/stream
Authorization: Bearer JWT_TOKEN
Accept: text/event-stream
```

Initial event:

```text
event: connected
data: ok
```

When an order changes:

```text
event: order-status
data: {"id":"order-id","status":"READY_FOR_PICKUP", ...}
```

If SSE disconnects, reconnect after a short delay and refresh `GET /api/vendor/orders`.

## Menu APIs

### List all menu items

```http
GET /api/vendor/menu
Authorization: Bearer JWT_TOKEN
```

This returns only menu items for the logged-in vendor's canteen.

### Create menu item

```http
POST /api/vendor/menu
Authorization: Bearer JWT_TOKEN
Content-Type: application/json
```

```json
{
  "name": "Veg Burger",
  "price": 80.00,
  "category_id": null,
  "description": "Fresh vegetable burger",
  "stock": 25,
  "is_available": true,
  "is_student_visible": true,
  "preparation_time_minutes": 10,
  "image_url": "/images/veg-burger.png"
}
```

### Update menu item or stock

```http
PATCH /api/vendor/menu/{itemId}
Authorization: Bearer JWT_TOKEN
Content-Type: application/json
```

```json
{
  "stock": 0,
  "is_available": false
}
```

Use `is_available: false` when an item is temporarily out of stock. The customer server will stop showing or accepting that item after the shared database is updated.

## Kitchen APIs

### Get kitchen settings

```http
GET /api/vendor/kitchen/settings
Authorization: Bearer JWT_TOKEN
```

### Update kitchen settings

```http
PATCH /api/vendor/kitchen/settings
Authorization: Bearer JWT_TOKEN
Content-Type: application/json
```

```json
{
  "base_prep_buffer_minutes": 5,
  "max_concurrent_orders": 20,
  "is_accepting_orders": false
}
```

When `is_accepting_orders` is `false`, the customer server must reject new checkout requests as kitchen closed.

## Staff APIs

### List staff

```http
GET /api/vendor/staff
Authorization: Bearer JWT_TOKEN
```

This returns only staff assigned to the logged-in vendor's canteen.

### Add staff member

```http
POST /api/vendor/staff
Authorization: Bearer JWT_TOKEN
Content-Type: application/json
```

```json
{
  "name": "Kitchen Staff",
  "role": "Kitchen Staff",
  "status": "active",
  "image_url": null
}
```

## Android Retrofit outline

```kotlin
interface VendorApi {
    @POST("api/vendor/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("api/vendor/orders")
    suspend fun getOrders(): List<VendorOrder>

    @PATCH("api/vendor/orders/{id}/status")
    suspend fun updateOrderStatus(
        @Path("id") id: String,
        @Body request: StatusRequest
    ): VendorOrder

    @GET("api/vendor/menu")
    suspend fun getMenu(): List<VendorMenuItem>
}
```

Add an OkHttp interceptor that attaches `Authorization: Bearer <token>` to protected requests. Store the token in encrypted Android storage rather than plain preferences.

## Error responses

Errors use this format:

```json
{
  "timestamp": "2026-07-14T12:00:00",
  "status": 400,
  "error": "Bad Request",
  "message": "Unsupported order status"
}
```

Common status codes:

| Code | Meaning |
|---|---|
| `200` | Successful request |
| `201` | Created |
| `400` | Invalid request or business rule failure |
| `401` | Missing or expired login token |
| `404` | Order or menu item does not exist |
| `500` | Server or database error |

## Communication flow

```text
Customer app
    -> Customer server : register with college + canteen, place order
Customer server
    -> PostgreSQL       : save order
Vendor server
    -> PostgreSQL       : read queue for vendor canteen only
Vendor app
    -> Vendor server    : update order status
Vendor server
    -> PostgreSQL       : save new status
Vendor server
    -> SSE              : notify vendor clients
Customer server
    -> SSE              : notify customer client
```

## Start the vendor server

```powershell
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```
## WebSocket order updates

Vendor clients can receive the same live order updates through WebSocket:

```text
ws://HOST:8001/api/vendor/orders/ws?token=VENDOR_JWT
```

The server first sends `{"event":"connected","data":"ok"}`. Order changes are sent as `{"event":"order-status","data":{...order...}}`.

## Vendor order acceptance and duplicate menu protection

New orders remain `PLACED` until the vendor accepts them. A vendor can switch automatic acceptance on or off with:

```http
PATCH /api/vendor/kitchen/settings
Authorization: Bearer VENDOR_JWT
Content-Type: application/json

{"auto_accept_orders": true}
```

The current setting is returned as `autoAcceptOrders`. When automatic acceptance is off, vendors may only use the normal progression: `PLACED` (or `SCHEDULED`) → `PREPARING` → `READY_FOR_PICKUP` → `DELIVERED`. Delivered orders are locked for vendors.

Duplicate menu names are prevented inside the same canteen, ignoring letter case and repeated spaces. Existing duplicate rows can be checked with:

```http
GET /api/vendor/menu/duplicates
Authorization: Bearer VENDOR_JWT
```
