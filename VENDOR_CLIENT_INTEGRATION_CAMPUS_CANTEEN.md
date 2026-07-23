# Vendor App Integration

After `POST /api/vendor/auth/login`, store the returned `vendor.canteenId` with the token and display the canteen name in the dashboard header.

Use the existing vendor endpoints without sending a canteen ID. The server obtains the canteen from the JWT and enforces isolation:

- `GET /api/vendor/menu`
- `POST /api/vendor/menu`
- `PATCH /api/vendor/menu/{itemId}`
- `GET /api/vendor/orders`
- `PATCH /api/vendor/orders/{orderId}/status`
- `GET /api/vendor/staff`

Do not allow the vendor app to choose another canteen. A separate vendor account is used for each canteen.
