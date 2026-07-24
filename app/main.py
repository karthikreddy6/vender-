from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.exceptions import register_exception_handlers
from app.models import KitchenSettings, VendorAccount
from app.routers import vendor, vendor_auth
from app.security import hash_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with AsyncSessionLocal() as db:
            settings = (await db.execute(select(KitchenSettings).where(KitchenSettings.id == 1))).scalar_one_or_none()
            if not settings:
                db.add(KitchenSettings(id=1, base_prep_buffer_minutes=3, max_concurrent_orders=20, is_accepting_orders=True))
            account = (await db.execute(select(VendorAccount).where(VendorAccount.email == "vendor@onfood.local"))).scalar_one_or_none()
            if not account:
                db.add(VendorAccount(name="OnFood Vendor", email="vendor@onfood.local", role="admin",
                                     hashed_password=hash_password("vendor_password")))
            else:
                # Upgrade legacy plain bcrypt password hash format to SHA-256 + bcrypt
                import bcrypt
                pwd_bytes = "vendor_password".encode('utf-8')
                hashed_bytes = account.hashed_password.encode('utf-8')
                if bcrypt.checkpw(pwd_bytes, hashed_bytes):
                    print("[Migration] Upgrading vendor@onfood.local password to SHA-256 + bcrypt format...")
                    account.hashed_password = hash_password("vendor_password")
            await db.commit()
    except Exception as exc:
        print(f"[Startup warning] {exc}. Run alembic upgrade head first.")

    # Start Postgres Event Bridge
    from app.pubsub import event_bridge
    from app.routers.vendor import vendor_stream, vendor_websocket_stream

    async def handle_incoming_event(event_data):
        event_type = event_data.get("event")
        if event_type in {"order_created", "order_status_updated"}:
            data = event_data.get("data")
            await vendor_stream.broadcast_to_user("all", "order-status", data)
            await vendor_websocket_stream.broadcast("order-status", data)

    await event_bridge.start(handle_incoming_event)

    yield

    await event_bridge.stop()


app = FastAPI(title="OnFood Vendor Server", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(vendor_auth.router)
app.include_router(vendor.router)
register_exception_handlers(app)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "UP", "service": "onfood-vendor-server", "port": 8001}
