from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class VendorLoginRequest(BaseModel):
    email: str
    password: str


class VendorLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    vendor: dict


class StatusRequest(BaseModel):
    status: str


class MenuUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    description: Optional[str] = None
    stock: Optional[int] = Field(default=None, ge=0)
    image_url: Optional[str] = None
    is_available: Optional[bool] = None
    is_student_visible: Optional[bool] = None
    preparation_time_minutes: Optional[int] = Field(default=None, ge=0)


class MenuCreateRequest(MenuUpdateRequest):
    name: str
    price: Decimal = Field(ge=0)
    category_id: Optional[UUID] = None


class KitchenUpdateRequest(BaseModel):
    base_prep_buffer_minutes: Optional[int] = Field(default=None, ge=0)
    max_concurrent_orders: Optional[int] = Field(default=None, ge=1)
    is_accepting_orders: Optional[bool] = None
    auto_accept_orders: Optional[bool] = None


class StaffRequest(BaseModel):
    name: str
    role: str
    status: str = "active"
    image_url: Optional[str] = None
