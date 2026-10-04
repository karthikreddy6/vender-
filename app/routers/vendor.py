import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.exceptions import BadRequestException, NotFoundException
from app.models import Canteen, Category, KitchenSettings, MenuItem, Order, OrderItem, OrderStatus, StaffMember
from app.security import get_current_vendor
from app.config import settings
from app.sse import SSEConnectionManager, WebSocketConnectionManager
from app.vendor_schemas import KitchenUpdateRequest, MenuCreateRequest, MenuUpdateRequest, StaffRequest, StatusRequest
import jwt

router = APIRouter(prefix="/api/vendor", tags=["Vendor"])
vendor_stream = SSEConnectionManager()
vendor_websocket_stream = WebSocketConnectionManager()

VENDOR_ORDER_TRANSITIONS = {
    OrderStatus.PLACED: {OrderStatus.PREPARING, OrderStatus.REJECTED},
    OrderStatus.SCHEDULED: {OrderStatus.PREPARING, OrderStatus.REJECTED},
    OrderStatus.PREPARING: {OrderStatus.READY_FOR_PICKUP, OrderStatus.REJECTED},
    OrderStatus.READY_FOR_PICKUP: {OrderStatus.DELIVERED},
}


def normalized_menu_name(name: str) -> str:
    return " ".join(name.split()).casefold()


async def ensure_unique_menu_name(db: AsyncSession, canteen_id, name: str, excluded_id: UUID | None = None) -> None:
    """Reject duplicate menu names inside one canteen, ignoring case and extra spaces."""
    target = normalized_menu_name(name)
    query = select(MenuItem.id, MenuItem.name).where(
        MenuItem.canteen_id == canteen_id,
        func.lower(func.btrim(func.regexp_replace(MenuItem.name, r'\s+', ' ', 'g'))) == target
    )
    if excluded_id is not None:
        query = query.where(MenuItem.id != excluded_id)
    result = await db.execute(query)
    existing = result.first()
    if existing:
        raise BadRequestException(f"Duplicate menu item: '{existing[1]}' already exists in this canteen")


def websocket_vendor_token(websocket: WebSocket) -> bool:
    """Validate vendor JWT from ?token= or an Authorization: Bearer header."""
    token = websocket.query_params.get("token")
    if not token:
        authorization = websocket.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:]
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], issuer=settings.JWT_ISSUER)
        return payload.get("role") in {"staff", "admin"}
    except jwt.InvalidTokenError:
        return False


def order_json(order: Order) -> dict:
    items_summary = ", ".join(
        f"{item.menu_item.name if item.menu_item else item.menu_item_id} x {item.quantity}"
        for item in order.items
    )
    student_name = order.user.name if order.user else "Student"
    placed_time = order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else None
    return {
        "id": str(order.id), "userId": order.user_id, "canteenId": str(order.canteen_id) if order.canteen_id else None, "status": order.status.value,
        "totalAmount": float(order.total_amount), "pickupNumber": order.pickup_number,
        "token": str(order.pickup_number) if order.pickup_number is not None else str(order.id)[:8],
        "studentName": student_name, "student_name": student_name,
        "rollNo": "", "roll_no": "", "branch": "",
        "itemsSummary": items_summary, "items_summary": items_summary,
        "total_amount": float(order.total_amount), "placed_time": placed_time,
        "scheduledDate": order.scheduled_date.isoformat() if order.scheduled_date else None,
        "scheduledSlotId": str(order.scheduled_slot_id) if order.scheduled_slot_id else None,
        "notes": order.notes, "createdAt": order.created_at.isoformat() if order.created_at else None,
        "paymentMethod": "Online / UPI" if order.notes and "UPI" in order.notes.upper() else "Cash on Counter",
        "payment_method": "Online / UPI" if order.notes and "UPI" in order.notes.upper() else "Cash on Counter",
        "paymentStatus": "Paid" if order.status == OrderStatus.DELIVERED else "Pay at Counter",
        "payment_status": "Paid" if order.status == OrderStatus.DELIVERED else "Pay at Counter",
        "items": [{"menuItemId": str(item.menu_item_id), "name": item.menu_item.name if item.menu_item else None,
                   "quantity": item.quantity, "price": str(item.price_at_time_of_order)} for item in order.items]
    }


@router.get("/orders")
async def orders(status: Optional[list[OrderStatus]] = Query(None), db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    query = select(Order).options(selectinload(Order.user), selectinload(Order.items).selectinload(OrderItem.menu_item)).where(Order.canteen_id == vendor.get("canteen_id")).order_by(Order.created_at.desc())
    if status:
        query = query.where(Order.status.in_(status))
    else:
        query = query.where(Order.status != OrderStatus.DELIVERED)
    result = await db.execute(query)
    return [order_json(item) for item in result.unique().scalars().all()]


@router.patch("/orders/{order_id}/status")
async def update_order(order_id: UUID, request: StatusRequest, db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    try:
        new_status = OrderStatus(request.status.upper())
    except ValueError:
        raise BadRequestException(f"Unsupported order status: {request.status}")
    result = await db.execute(select(Order).options(selectinload(Order.user), selectinload(Order.items).selectinload(OrderItem.menu_item)).where(Order.id == order_id, Order.canteen_id == vendor.get("canteen_id")))
    order = result.unique().scalar_one_or_none()
    if not order:
        raise NotFoundException(f"Order not found: {order_id}")
    if order.status == OrderStatus.DELIVERED and vendor.get("role") != "admin":
        raise BadRequestException("Delivered orders are locked. Only an admin can correct them.")
    if vendor.get("role") != "admin" and new_status not in VENDOR_ORDER_TRANSITIONS.get(order.status, set()):
        raise BadRequestException(f"Invalid vendor order transition: {order.status.value} -> {new_status.value}")
    old_status = order.status
    order.status = new_status
    if new_status == OrderStatus.READY_FOR_PICKUP:
        order.actual_ready_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # ── Stock Management ──────────────────────────────────────────────
    # Deduct stock when vendor ACCEPTS the order (transitions to PREPARING).
    # This "holds" the quantity so other students cannot order sold-out items.
    if new_status == OrderStatus.PREPARING and old_status in (OrderStatus.PLACED, OrderStatus.SCHEDULED):
        for item in order.items:
            menu_item = item.menu_item
            if not menu_item and item.menu_item_id:
                mi_result = await db.execute(select(MenuItem).where(MenuItem.id == item.menu_item_id))
                menu_item = mi_result.scalar_one_or_none()
            if menu_item:
                menu_item.stock = max(0, (menu_item.stock or 0) - item.quantity)
                # Auto-disable the item if stock hits zero
                if menu_item.stock <= 0:
                    menu_item.is_available = False

    # Restore stock when order is REJECTED or CANCELLED after it was already accepted.
    # If the order was still PLACED/SCHEDULED (never accepted), nothing was deducted.
    if new_status in (OrderStatus.REJECTED, OrderStatus.CANCELLED) and old_status == OrderStatus.PREPARING:
        for item in order.items:
            menu_item = item.menu_item
            if not menu_item and item.menu_item_id:
                mi_result = await db.execute(select(MenuItem).where(MenuItem.id == item.menu_item_id))
                menu_item = mi_result.scalar_one_or_none()
            if menu_item:
                menu_item.stock = (menu_item.stock or 0) + item.quantity
                # Only re-enable the item if it was auto-disabled by stock
                # reaching zero (stock was 0 before restore). Don't override
                # a manual disable by the vendor.
                if not menu_item.is_available and (menu_item.stock - item.quantity) <= 0:
                    menu_item.is_available = True
    await db.commit()
    payload = order_json(order)
    canteen_channel = f"canteen_{order.canteen_id}" if order.canteen_id else "all"
    await vendor_stream.broadcast_to_user(canteen_channel, "order-status", payload)
    await vendor_websocket_stream.broadcast("order-status", payload)

    # Notify event bridge (real-time sync to customer server)
    try:
        from app.pubsub import event_bridge
        await event_bridge.notify("order_status_updated", payload)
    except Exception as e:
        print(f"[Bridge Error] Failed to publish status update to Postgres: {e}")

    return payload


@router.get("/orders/stream")
async def stream_orders(vendor=Depends(get_current_vendor)):
    canteen_channel = f"canteen_{vendor.get('canteen_id')}" if vendor.get("canteen_id") else "all"
    async def event_generator():
        queue = await vendor_stream.subscribe(canteen_channel)
        try:
            yield {"event": "connected", "data": "ok"}
            while True:
                yield await queue.get()
        except asyncio.CancelledError:
            pass
        finally:
            vendor_stream.unsubscribe(canteen_channel, queue)
    return EventSourceResponse(event_generator(), ping=30)


@router.websocket("/orders/ws")
async def order_websocket(websocket: WebSocket):
    """Live vendor order updates over WebSocket.

    Connect using ws://HOST:8001/api/vendor/orders/ws?token=VENDOR_JWT.
    """
    if not websocket_vendor_token(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Vendor authentication required")
        return
    await vendor_websocket_stream.connect(websocket)
    try:
        await websocket.send_json({"event": "connected", "data": "ok"})
        while True:
            # Keep the socket open and allow mobile clients to send a ping message.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        vendor_websocket_stream.disconnect(websocket)


@router.get("/menu")
async def get_menu(db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    result = await db.execute(select(MenuItem).where(MenuItem.canteen_id == vendor.get("canteen_id")).order_by(MenuItem.name))
    return [menu_json(item) for item in result.scalars().all()]


@router.get("/menu/duplicates")
async def menu_duplicates(db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    """List already-existing duplicate names for the logged-in vendor's canteen."""
    result = await db.execute(select(MenuItem.id, MenuItem.name).where(MenuItem.canteen_id == vendor.get("canteen_id")).order_by(MenuItem.name))
    groups: dict[str, list[dict]] = {}
    for item_id, name in result.all():
        groups.setdefault(normalized_menu_name(name), []).append({"id": str(item_id), "name": name})
    return [{"normalizedName": key, "items": items} for key, items in groups.items() if len(items) > 1]


def menu_json(item: MenuItem) -> dict:
    category_id = str(item.category_id) if item.category_id else None
    price = float(item.price)
    return {"id": str(item.id), "name": item.name, "price": price, "canteenId": str(item.canteen_id) if item.canteen_id else None, "description": item.description,
            "categoryId": category_id, "category_id": category_id, "imageUrl": item.image_url, "image_url": item.image_url,
            "stock": item.stock, "isAvailable": item.is_available, "is_available": item.is_available,
            "isStudentVisible": item.is_student_visible, "is_student_visible": item.is_student_visible,
            "preparationTimeMinutes": item.preparation_time_minutes, "preparation_time_minutes": item.preparation_time_minutes}


@router.post("/menu", status_code=201)
async def create_menu(request: MenuCreateRequest, db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    await ensure_unique_menu_name(db, vendor.get("canteen_id"), request.name)
    item = MenuItem(name=request.name, price=request.price, category_id=request.category_id,
                    description=request.description, stock=request.stock or 0,
                    image_url=request.image_url, is_available=request.is_available if request.is_available is not None else True,
                    is_student_visible=request.is_student_visible if request.is_student_visible is not None else True,
                    preparation_time_minutes=request.preparation_time_minutes or 10,
                    canteen_id=vendor.get("canteen_id"))
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return menu_json(item)


@router.patch("/menu/{item_id}")
async def update_menu(item_id: UUID, request: MenuUpdateRequest, db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    result = await db.execute(select(MenuItem).where(MenuItem.id == item_id, MenuItem.canteen_id == vendor.get("canteen_id")))
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundException(f"Menu item not found: {item_id}")
    if request.name is not None:
        await ensure_unique_menu_name(db, vendor.get("canteen_id"), request.name, item.id)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    # Auto-enable item when vendor restocks (sets stock > 0)
    if request.stock is not None and request.stock > 0 and not item.is_available:
        item.is_available = True
    await db.commit()
    await db.refresh(item)
    return menu_json(item)


async def get_canteen_or_404(db: AsyncSession, canteen_id) -> Canteen:
    canteen = (await db.execute(select(Canteen).where(Canteen.id == canteen_id))).scalar_one_or_none()
    if not canteen:
        raise NotFoundException("Canteen not found for vendor account")
    return canteen


@router.get("/kitchen/settings")
async def get_kitchen(db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    result = await db.execute(select(KitchenSettings).where(KitchenSettings.id == 1))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = KitchenSettings(id=1)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    canteen = await get_canteen_or_404(db, vendor.get("canteen_id"))
    return {"basePrepBufferMinutes": settings.base_prep_buffer_minutes, "maxConcurrentOrders": settings.max_concurrent_orders,
            "isAcceptingOrders": settings.is_accepting_orders, "autoAcceptOrders": canteen.auto_accept_orders}


@router.patch("/kitchen/settings")
async def update_kitchen(request: KitchenUpdateRequest, db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    result = await db.execute(select(KitchenSettings).where(KitchenSettings.id == 1))
    settings = result.scalar_one_or_none() or KitchenSettings(id=1)
    update_data = request.model_dump(exclude_unset=True)
    auto_accept_orders = update_data.pop("auto_accept_orders", None)
    for field, value in update_data.items():
        setattr(settings, field, value)
    db.add(settings)
    if auto_accept_orders is not None:
        canteen = await get_canteen_or_404(db, vendor.get("canteen_id"))
        canteen.auto_accept_orders = auto_accept_orders
    await db.commit()
    return await get_kitchen(db, vendor)


@router.get("/staff")
async def get_staff(db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    result = await db.execute(select(StaffMember).where(StaffMember.canteen_id == vendor.get("canteen_id")).order_by(StaffMember.id))
    return [{"id": str(member.id), "name": member.name, "role": member.role, "status": member.status,
             "imageUrl": member.image_url, "image_url": member.image_url}
            for member in result.scalars().all()]


@router.post("/staff", status_code=201)
async def add_staff(request: StaffRequest, db: AsyncSession = Depends(get_db), vendor=Depends(get_current_vendor)):
    member = StaffMember(**request.model_dump(), canteen_id=vendor.get("canteen_id"))
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return {"id": str(member.id), "name": member.name, "role": member.role, "status": member.status,
            "imageUrl": member.image_url, "image_url": member.image_url}


# ── Image Upload & Management ─────────────────────────────────────
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/upload/image", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    vendor=Depends(get_current_vendor)
):
    """Allows vendors to upload photos for menu items or canteen assets."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise BadRequestException(f"Unsupported file format '{ext}'. Allowed: JPG, JPEG, PNG, WEBP, GIF")

    if file.content_type and not file.content_type.startswith("image/"):
        raise BadRequestException(f"Invalid content type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE_BYTES:
        raise BadRequestException(f"File size ({len(contents) / (1024*1024):.1f}MB) exceeds 10MB limit")

    canteen_id = str(vendor.get("canteen_id") or "common")
    canteen_upload_dir = os.path.join(settings.UPLOAD_DIR, "menu_items", canteen_id)
    os.makedirs(canteen_upload_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(canteen_upload_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    relative_url = f"/uploads/menu_items/{canteen_id}/{unique_filename}"
    return {
        "imageUrl": relative_url,
        "image_url": relative_url,
        "filename": unique_filename,
        "sizeBytes": len(contents)
    }


@router.get("/images")
async def list_images(
    db: AsyncSession = Depends(get_db),
    vendor=Depends(get_current_vendor)
):
    """Returns all images uploaded by this vendor as well as images assigned to menu items."""
    canteen_id = str(vendor.get("canteen_id") or "common")
    canteen_upload_dir = os.path.join(settings.UPLOAD_DIR, "menu_items", canteen_id)

    uploaded_images = []
    if os.path.exists(canteen_upload_dir):
        for entry in os.scandir(canteen_upload_dir):
            if entry.is_file():
                stat = entry.stat()
                uploaded_images.append({
                    "filename": entry.name,
                    "imageUrl": f"/uploads/menu_items/{canteen_id}/{entry.name}",
                    "image_url": f"/uploads/menu_items/{canteen_id}/{entry.name}",
                    "sizeBytes": stat.st_size,
                    "uploadedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                })
        uploaded_images.sort(key=lambda x: x["uploadedAt"], reverse=True)

    # Menu items currently using an image
    menu_result = await db.execute(
        select(MenuItem.id, MenuItem.name, MenuItem.image_url)
        .where(MenuItem.canteen_id == vendor.get("canteen_id"), MenuItem.image_url.isnot(None))
    )
    assigned_images = [
        {"menuItemId": str(row[0]), "menuItemName": row[1], "imageUrl": row[2]}
        for row in menu_result.all()
    ]

    # Common library images from onfoodserver/app/static/images
    library_images = []
    if os.path.isdir(settings.STATIC_IMAGES_DIR):
        for entry in os.scandir(settings.STATIC_IMAGES_DIR):
            if entry.is_file() and not entry.name.startswith("."):
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in ALLOWED_IMAGE_EXTENSIONS:
                    library_images.append({
                        "filename": entry.name,
                        "imageUrl": f"/images/{entry.name}",
                        "image_url": f"/images/{entry.name}",
                    })
        library_images.sort(key=lambda x: x["filename"].lower())

    return {
        "canteenId": canteen_id,
        "uploadedImages": uploaded_images,
        "assignedImages": assigned_images,
        "libraryImages": library_images
    }


@router.delete("/images/{filename}")
async def delete_image(
    filename: str,
    vendor=Depends(get_current_vendor)
):
    """Deletes an uploaded image from the canteen's upload directory."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise BadRequestException("Invalid filename")

    canteen_id = str(vendor.get("canteen_id") or "common")
    file_path = os.path.join(settings.UPLOAD_DIR, "menu_items", canteen_id, filename)
    if not os.path.exists(file_path):
        raise NotFoundException(f"Image '{filename}' not found")

    os.remove(file_path)
    return {"message": f"Image '{filename}' deleted successfully"}

