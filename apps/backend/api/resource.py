import json
from datetime import date
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from apps.backend.db import get_connection

router = APIRouter()

ResourceStatus = Literal["active", "inactive"]

TRANSPORT_FIELDS = (
    "id", "destination", "resource_name", "supplier_name",
    "transport_type", "departure_city", "arrival_city",
    "cost_price", "sale_price", "stock_quantity", "sold_quantity",
    "reserved_quantity", "currency", "available_start_date",
    "available_end_date", "available_dates", "status", "created_at",
)
HOTEL_ROOM_FIELDS = (
    "id", "destination", "resource_name", "supplier_name",
    "hotel_name", "room_type", "breakfast_included", "max_occupancy",
    "cost_price", "sale_price", "stock_quantity", "sold_quantity",
    "reserved_quantity", "currency", "available_start_date",
    "available_end_date", "available_dates", "status", "created_at",
)
ATTRACTION_TICKET_FIELDS = (
    "id", "destination", "resource_name", "supplier_name",
    "cost_price", "sale_price", "stock_quantity", "sold_quantity",
    "reserved_quantity", "currency", "available_start_date",
    "available_end_date", "available_dates", "status", "created_at",
)
RESTAURANT_MEAL_FIELDS = (
    "id", "destination", "resource_name", "supplier_name",
    "meal_type", "price_per_person", "cost_price", "sale_price",
    "stock_quantity", "sold_quantity", "reserved_quantity", "currency",
    "available_start_date", "available_end_date", "available_dates",
    "status", "created_at",
)
ACTIVITY_FIELDS = (
    "id", "destination", "resource_name", "supplier_name",
    "activity_type", "duration", "suitable_people", "cost_price",
    "sale_price", "stock_quantity", "sold_quantity", "reserved_quantity",
    "currency", "available_start_date", "available_end_date",
    "available_dates", "status", "created_at",
)


class ResourceCreateBase(BaseModel):
    destination: str = Field(min_length=1)
    resource_name: str = Field(min_length=1)
    supplier_name: str = Field(min_length=1)
    cost_price: float = Field(ge=0, allow_inf_nan=False)
    sale_price: float = Field(ge=0, allow_inf_nan=False)
    stock_quantity: int = Field(default=0, ge=0)
    sold_quantity: int = Field(default=0, ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    available_start_date: date | None = None
    available_end_date: date | None = None
    available_dates: list[date] | None = None
    status: ResourceStatus = "active"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value):
        return value.upper()

    @model_validator(mode="after")
    def validate_availability_range(self):
        if (
            self.available_start_date is not None
            and self.available_end_date is not None
            and self.available_start_date > self.available_end_date
        ):
            raise ValueError("可用开始日期不能晚于结束日期")
        if self.sold_quantity + self.reserved_quantity > self.stock_quantity:
            raise ValueError("已售数量与预留数量之和不能大于总库存")
        return self


class TransportResourceCreate(ResourceCreateBase):
    transport_type: str = Field(min_length=1)
    departure_city: str = Field(min_length=1)
    arrival_city: str = Field(min_length=1)


class HotelRoomResourceCreate(ResourceCreateBase):
    hotel_name: str = Field(min_length=1)
    room_type: str = Field(min_length=1)
    breakfast_included: bool = False
    max_occupancy: int = Field(ge=1)


class AttractionTicketResourceCreate(ResourceCreateBase):
    pass


class RestaurantMealResourceCreate(ResourceCreateBase):
    meal_type: str = Field(min_length=1)
    price_per_person: float = Field(ge=0, allow_inf_nan=False)


class ActivityResourceCreate(ResourceCreateBase):
    activity_type: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    suitable_people: str = Field(min_length=1)


def to_database_value(value):
    if isinstance(value, list):
        date_values = [
            item.isoformat() if isinstance(item, date) else item
            for item in value
        ]
        return json.dumps(date_values, ensure_ascii=False)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


def serialize_resource(row, boolean_fields=()):
    resource = dict(row)
    for field_name in boolean_fields:
        resource[field_name] = bool(resource[field_name])
    raw_available_dates = resource.get("available_dates")
    if raw_available_dates:
        try:
            parsed_dates = json.loads(raw_available_dates)
            resource["available_dates"] = (
                parsed_dates if isinstance(parsed_dates, list) else []
            )
        except json.JSONDecodeError:
            resource["available_dates"] = []
    else:
        resource["available_dates"] = []
    resource["available_quantity"] = (
        resource["stock_quantity"]
        - resource["sold_quantity"]
        - resource["reserved_quantity"]
    )
    return resource


def is_available_on(resource, available_on):
    if available_on is None:
        return True

    available_date = available_on.isoformat()
    if resource["available_dates"]:
        return available_date in resource["available_dates"]

    start_date = resource["available_start_date"]
    end_date = resource["available_end_date"]
    return (
        (start_date is None or start_date <= available_date)
        and (end_date is None or end_date >= available_date)
    )


def create_resource(table_name, fields, resource, boolean_fields=()):
    payload = resource.model_dump()
    insert_fields = fields[1:-1]
    columns = ", ".join(insert_fields)
    placeholders = ", ".join("?" for _ in insert_fields)
    values = [to_database_value(payload[field]) for field in insert_fields]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    resource_id = cursor.lastrowid

    cursor.execute(
        f"SELECT {', '.join(fields)} FROM {table_name} WHERE id = ?",
        (resource_id,),
    )
    created_resource = serialize_resource(cursor.fetchone(), boolean_fields)
    conn.close()

    return {
        "success": True,
        "resource": created_resource,
    }


def list_resources(
    table_name,
    fields,
    destination=None,
    status=None,
    supplier_name=None,
    max_cost_price=None,
    available_on=None,
    has_stock=None,
    boolean_fields=(),
):
    sql = f"SELECT {', '.join(fields)} FROM {table_name}"
    conditions = []
    params = []

    if destination:
        conditions.append("destination LIKE ?")
        params.append(f"%{destination}%")

    if status:
        conditions.append("status = ?")
        params.append(status)

    if supplier_name:
        conditions.append("supplier_name LIKE ?")
        params.append(f"%{supplier_name}%")

    if max_cost_price is not None:
        conditions.append("cost_price <= ?")
        params.append(max_cost_price)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY id DESC"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    resources = [
        serialize_resource(row, boolean_fields)
        for row in cursor.fetchall()
    ]
    conn.close()

    resources = [
        resource
        for resource in resources
        if is_available_on(resource, available_on)
    ]
    if has_stock is True:
        resources = [
            resource for resource in resources
            if resource["available_quantity"] > 0
        ]
    elif has_stock is False:
        resources = [
            resource for resource in resources
            if resource["available_quantity"] <= 0
        ]

    return {
        "success": True,
        "count": len(resources),
        "resources": resources,
    }


@router.post("/resources/transport")
def create_transport_resource(resource: TransportResourceCreate):
    return create_resource(
        "travel_transport_resources",
        TRANSPORT_FIELDS,
        resource,
    )


@router.get("/resources/transport")
def get_transport_resources(
    destination: str | None = None,
    status: ResourceStatus | None = None,
    supplier_name: str | None = None,
    max_cost_price: float | None = Query(default=None, ge=0),
    available_on: date | None = None,
    has_stock: bool | None = None,
):
    return list_resources(
        "travel_transport_resources",
        TRANSPORT_FIELDS,
        destination,
        status,
        supplier_name,
        max_cost_price,
        available_on,
        has_stock,
    )


@router.post("/resources/hotel-rooms")
def create_hotel_room_resource(resource: HotelRoomResourceCreate):
    return create_resource(
        "hotel_room_resources",
        HOTEL_ROOM_FIELDS,
        resource,
        boolean_fields=("breakfast_included",),
    )


@router.get("/resources/hotel-rooms")
def get_hotel_room_resources(
    destination: str | None = None,
    status: ResourceStatus | None = None,
    supplier_name: str | None = None,
    max_cost_price: float | None = Query(default=None, ge=0),
    available_on: date | None = None,
    has_stock: bool | None = None,
):
    return list_resources(
        "hotel_room_resources",
        HOTEL_ROOM_FIELDS,
        destination,
        status,
        supplier_name,
        max_cost_price,
        available_on,
        has_stock,
        boolean_fields=("breakfast_included",),
    )


@router.post("/resources/attraction-tickets")
def create_attraction_ticket_resource(resource: AttractionTicketResourceCreate):
    return create_resource(
        "attraction_ticket_resources",
        ATTRACTION_TICKET_FIELDS,
        resource,
    )


@router.get("/resources/attraction-tickets")
def get_attraction_ticket_resources(
    destination: str | None = None,
    status: ResourceStatus | None = None,
    supplier_name: str | None = None,
    max_cost_price: float | None = Query(default=None, ge=0),
    available_on: date | None = None,
    has_stock: bool | None = None,
):
    return list_resources(
        "attraction_ticket_resources",
        ATTRACTION_TICKET_FIELDS,
        destination,
        status,
        supplier_name,
        max_cost_price,
        available_on,
        has_stock,
    )


@router.post("/resources/restaurant-meals")
def create_restaurant_meal_resource(resource: RestaurantMealResourceCreate):
    return create_resource(
        "restaurant_meal_resources",
        RESTAURANT_MEAL_FIELDS,
        resource,
    )


@router.get("/resources/restaurant-meals")
def get_restaurant_meal_resources(
    destination: str | None = None,
    status: ResourceStatus | None = None,
    supplier_name: str | None = None,
    max_cost_price: float | None = Query(default=None, ge=0),
    available_on: date | None = None,
    has_stock: bool | None = None,
):
    return list_resources(
        "restaurant_meal_resources",
        RESTAURANT_MEAL_FIELDS,
        destination,
        status,
        supplier_name,
        max_cost_price,
        available_on,
        has_stock,
    )


@router.post("/resources/activities")
def create_activity_resource(resource: ActivityResourceCreate):
    return create_resource(
        "activity_resources",
        ACTIVITY_FIELDS,
        resource,
    )


@router.get("/resources/activities")
def get_activity_resources(
    destination: str | None = None,
    status: ResourceStatus | None = None,
    supplier_name: str | None = None,
    max_cost_price: float | None = Query(default=None, ge=0),
    available_on: date | None = None,
    has_stock: bool | None = None,
):
    return list_resources(
        "activity_resources",
        ACTIVITY_FIELDS,
        destination,
        status,
        supplier_name,
        max_cost_price,
        available_on,
        has_stock,
    )
