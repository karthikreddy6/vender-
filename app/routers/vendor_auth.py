from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.exceptions import BadRequestException, UnauthenticatedException
from app.models import VendorAccount
from app.security import create_access_token, get_current_vendor, hash_password, verify_password
from app.vendor_schemas import VendorLoginRequest, VendorLoginResponse

router = APIRouter(prefix="/api/vendor/auth", tags=["Vendor Auth"])


@router.post("/login", response_model=VendorLoginResponse)
async def login(request: VendorLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VendorAccount).where(VendorAccount.email == request.email.lower()))
    vendor = result.scalar_one_or_none()
    if not vendor or not vendor.is_active or not verify_password(request.password, vendor.hashed_password):
        raise UnauthenticatedException("Invalid vendor email or password")
    return VendorLoginResponse(
        access_token=create_access_token(vendor.id, vendor.role, vendor.canteen_id),
        vendor={"id": vendor.id, "name": vendor.name, "email": vendor.email, "role": vendor.role, "canteenId": str(vendor.canteen_id) if vendor.canteen_id else None},
    )


@router.get("/me")
async def me(vendor=Depends(get_current_vendor), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VendorAccount).where(VendorAccount.id == vendor["id"]))
    account = result.scalar_one_or_none()
    if not account:
        raise UnauthenticatedException("Vendor account not found")
    return {"id": account.id, "name": account.name, "email": account.email, "role": account.role, "canteenId": str(account.canteen_id) if account.canteen_id else None}
