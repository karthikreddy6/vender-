# Vendor Canteen Scoping

Each vendor account is linked to exactly one canteen through `vendor_accounts.canteen_id`.

The college selected by the student only controls which canteens they can access. Vendor login returns `canteenId` and places it in the JWT. Vendor order, menu, and staff endpoints only return or modify records belonging to that canteen.

Demo accounts:

- `central@onfood.local` / `vendor_password`
- `hostel@onfood.local` / `vendor_password`
- `arts@onfood.local` / `vendor_password`
- `science@onfood.local` / `vendor_password`
