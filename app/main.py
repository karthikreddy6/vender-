from contextlib import asynccontextmanager
import os
import bcrypt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.exceptions import register_exception_handlers
from app.models import KitchenSettings, VendorAccount
from app.routers import vendor, vendor_auth
from app.security import hash_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with AsyncSessionLocal() as db:
            kitchen_cfg = (await db.execute(select(KitchenSettings).where(KitchenSettings.id == 1))).scalar_one_or_none()
            if not kitchen_cfg:
                db.add(KitchenSettings(id=1, base_prep_buffer_minutes=3, max_concurrent_orders=20, is_accepting_orders=True))
            account = (await db.execute(select(VendorAccount).where(VendorAccount.email == "vendor@onfood.local"))).scalar_one_or_none()
            if not account:
                db.add(VendorAccount(name="OnFood Vendor", email="vendor@onfood.local", role="admin",
                                     hashed_password=hash_password("vendor_password")))
            else:
                # Upgrade legacy plain bcrypt password hash format to SHA-256 + bcrypt
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
            canteen_id = data.get("canteenId") if data else None
            channel = f"canteen_{canteen_id}" if canteen_id else "all"
            await vendor_stream.broadcast_to_user(channel, "order-status", data)
            await vendor_websocket_stream.broadcast("order-status", data)

    await event_bridge.start(handle_incoming_event)

    yield

    await event_bridge.stop()


app = FastAPI(title="OnFood Vendor Server", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

# Ensure uploads folder exists and mount static route
os.makedirs(os.path.join(settings.UPLOAD_DIR, "menu_items"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Mount /images to serve static dish images from onfoodserver/app/static/images
if os.path.isdir(settings.STATIC_IMAGES_DIR):
    print(f"[Static] Mounting /images from {settings.STATIC_IMAGES_DIR}")
    app.mount("/images", StaticFiles(directory=settings.STATIC_IMAGES_DIR), name="images")
else:
    print(f"[Static Warning] Static images dir '{settings.STATIC_IMAGES_DIR}' not found.")

app.include_router(vendor_auth.router)
app.include_router(vendor.router)
register_exception_handlers(app)


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "UP", "service": "onfood-vendor-server", "port": 8001}
