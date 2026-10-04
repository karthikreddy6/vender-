import asyncio
import datetime
import json
import uuid
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.models import Order, OrderItem, OrderStatus, MenuItem, User, Canteen


async def create_demo_orders():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as db:
        # 1. Find Central Canteen
        canteen_query = await db.execute(
            select(Canteen).where(func.lower(Canteen.name).like("%central%"))
        )
        canteen = canteen_query.scalar_one_or_none()
        if not canteen:
            print("Central Canteen not found!")
            return

        print(f"Using Canteen: {canteen.name} ({canteen.id})")

        # 2. Find Users
        users_query = await db.execute(select(User))
        users = users_query.scalars().all()
        if not users:
            print("No users found in database!")
            return

        user_map = {u.name: u for u in users}
        default_user = users[0]

        # 3. Find Menu Items in Central Canteen
        menu_query = await db.execute(
            select(MenuItem).where(MenuItem.canteen_id == canteen.id)
        )
        menu_items = {mi.name: mi for mi in menu_query.scalars().all()}
        if not menu_items:
            print("No menu items found for Central Canteen!")
            return

        today = datetime.date.today()
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        # Get latest pickup number for today
        max_num_query = await db.execute(
            select(func.max(Order.pickup_number)).where(
                Order.canteen_id == canteen.id,
                Order.pickup_date == today,
            )
        )
        current_max = max_num_query.scalar() or 0

        # Define 5 demo orders
        demo_orders_spec = [
            {
                "user": user_map.get("Karthik", default_user),
                "status": OrderStatus.PLACED,
                "notes": "Extra spicy please",
                "items": [
                    ("Chicken Biryani", 1),
                    ("Garlic Naan", 2),
                ],
            },
            {
                "user": user_map.get("jk", default_user),
                "status": OrderStatus.PLACED,
                "notes": "Please keep butter separate",
                "items": [
                    ("Pav Bhaji", 2),
                    ("Jalebi", 1),
                ],
            },
            {
                "user": user_map.get("Premium User", default_user),
                "status": OrderStatus.PREPARING,
                "notes": "Less spicy, extra gravy",
                "items": [
                    ("Butter Chicken", 1),
                    ("Garlic Naan", 2),
                ],
            },
            {
                "user": user_map.get("Karthik", default_user),
                "status": OrderStatus.READY_FOR_PICKUP,
                "notes": "Quick pickup",
                "items": [
                    ("Veg Dum Biryani", 1),
                    ("Chak-Hao Kheer", 1),
                ],
            },
            {
                "user": user_map.get("jk", default_user),
                "status": OrderStatus.DELIVERED,
                "notes": "Table 4 delivery",
                "items": [
                    ("Dosa", 1),
                    ("Sambar", 1),
                ],
            },
        ]

        created_orders = []

        for i, spec in enumerate(demo_orders_spec, 1):
            pickup_num = current_max + i
            user = spec["user"]
            status = spec["status"]

            # Calculate items and total
            order_items_to_add = []
            total = Decimal("0.00")

            for item_name, qty in spec["items"]:
                mi = menu_items.get(item_name)
                if not mi:
                    # fallback to any available menu item
                    mi = list(menu_items.values())[0]
                price = Decimal(str(mi.price))
                total += price * qty
                order_items_to_add.append((mi, qty, price))

            order_id = uuid.uuid4()
            order = Order(
                id=order_id,
                user_id=str(user.id),
                user_roll_number=user.roll_number or f"ROLL{pickup_num:03d}",
                order_token=str(pickup_num),
                canteen_id=canteen.id,
                total_amount=total,
                discount_amount=Decimal("0.00"),
                status=status,
                pickup_number=pickup_num,
                pickup_date=today,
                notes=spec["notes"],
                created_at=now - datetime.timedelta(minutes=(5 - i) * 8),
                estimated_ready_at=now + datetime.timedelta(minutes=15) if status in (OrderStatus.PLACED, OrderStatus.PREPARING) else None,
                actual_ready_at=now if status in (OrderStatus.READY_FOR_PICKUP, OrderStatus.DELIVERED) else None,
            )
            db.add(order)

            for mi, qty, price in order_items_to_add:
                order_item = OrderItem(
                    id=uuid.uuid4(),
                    order_id=order_id,
                    menu_item_id=mi.id,
                    quantity=qty,
                    price_at_time_of_order=price,
                )
                db.add(order_item)

            created_orders.append({
                "id": str(order_id),
                "token": str(pickup_num),
                "status": status.value,
                "student": user.name,
                "total": float(total),
                "items": ", ".join(f"{name} x{qty}" for name, qty in spec["items"]),
                "notes": spec["notes"],
            })

        await db.commit()
        print(f"Successfully committed {len(created_orders)} demo orders!")

        # Broadcast real-time NOTIFY event for vendor app
        try:
            import asyncpg
            dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            pg_conn = await asyncpg.connect(dsn)
            for o in created_orders:
                payload = json.dumps({
                    "event": "order_created",
                    "data": {
                        "id": o["id"],
                        "token": o["token"],
                        "pickupNumber": int(o["token"]),
                        "status": o["status"],
                        "student_name": o["student"],
                        "total_amount": o["total"],
                        "items_summary": o["items"],
                        "notes": o["notes"],
                        "canteenId": str(canteen.id),
                    }
                })
                safe_payload = payload.replace("'", "''")
                await pg_conn.execute(f"NOTIFY onfood_events, '{safe_payload}'")
            await pg_conn.close()
            print("Emitted NOTIFY events on 'onfood_events' channel for real-time dashboards.")
        except Exception as e:
            print(f"Notice: could not emit pg notify: {e}")

        print("\nCreated Orders Summary:")
        print("-" * 80)
        for o in created_orders:
            print(f"Token #{o['token']} | Status: {o['status']:<16} | Student: {o['student']:<12} | Total: Rs. {o['total']:<6} | {o['items']}")
        print("-" * 80)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_demo_orders())
