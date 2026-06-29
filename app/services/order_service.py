import json
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.database.postgres import get_db_cursor
from app.models.schemas import (
    OrderCreate,
    OrderResponse,
    OrderStatusUpdate,
    BillResponse,
)


# ─────────────────────────────────────────────
#  Price fetching from Pinecone
# ─────────────────────────────────────────────

def _get_price_from_menu(dish_name: str) -> float:
    """Search Pinecone for dish price automatically."""
    try:
        from app.services.chat_service import _query_pinecone, _get_price_from_menu as fetch_price
        return fetch_price(dish_name)
    except Exception:
        return 0.0


def _enrich_items_with_prices(items: list[dict]) -> list[dict]:
    """
    Automatically fetch prices from menu PDF via Pinecone.
    Customer only provides dish name and quantity.
    """
    try:
        from app.services.chat_service import _get_price_from_menu
        enriched = []
        for item in items:
            dish_name = item.get("menu_item", "")
            quantity = item.get("quantity", 1)
            price = item.get("price", 0)

            # Auto-fetch price if not provided or zero
            if not price or price == 0:
                price = _get_price_from_menu(dish_name)

            enriched.append({
                "menu_item": dish_name,
                "quantity": quantity,
                "price": price,
                "subtotal": price * quantity,
            })
        return enriched
    except Exception:
        return items


# ─────────────────────────────────────────────
#  Order CRUD
# ─────────────────────────────────────────────

def create_order(user_id: int, order_data: OrderCreate) -> OrderResponse:
    """Create a new order — prices fetched automatically from menu."""
    raw_items = [item.model_dump() for item in order_data.items]

    # Auto-fetch prices from Pinecone
    items = _enrich_items_with_prices(raw_items)

    # Calculate total
    total_amount = sum(item.get("subtotal", item.get("price", 0) * item.get("quantity", 1)) for item in items)

    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            """INSERT INTO orders (user_id, items, total_amount, special_instructions, status)
               VALUES (%s, %s, %s, %s, 'pending')
               RETURNING id, user_id, items, total_amount, status, special_instructions, created_at, updated_at""",
            (
                user_id,
                json.dumps(items),
                total_amount,
                order_data.special_instructions,
            ),
        )
        order = cur.fetchone()

    return OrderResponse(
        id=order["id"],
        user_id=order["user_id"],
        items=order["items"],
        total_amount=float(order["total_amount"]),
        status=order["status"],
        special_instructions=order["special_instructions"],
        created_at=order["created_at"],
        updated_at=order["updated_at"],
    )


def get_order(order_id: int, user_id: Optional[int] = None) -> OrderResponse:
    """Get a specific order."""
    with get_db_cursor() as cur:
        if user_id:
            cur.execute(
                """SELECT id, user_id, items, total_amount, status, special_instructions, created_at, updated_at
                   FROM orders WHERE id = %s AND user_id = %s""",
                (order_id, user_id),
            )
        else:
            cur.execute(
                """SELECT id, user_id, items, total_amount, status, special_instructions, created_at, updated_at
                   FROM orders WHERE id = %s""",
                (order_id,),
            )
        order = cur.fetchone()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return OrderResponse(
        id=order["id"],
        user_id=order["user_id"],
        items=order["items"],
        total_amount=float(order["total_amount"]),
        status=order["status"],
        special_instructions=order["special_instructions"],
        created_at=order["created_at"],
        updated_at=order["updated_at"],
    )


def list_orders(
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[OrderResponse], int]:
    """List orders, optionally filtered by user."""
    with get_db_cursor() as cur:
        if user_id:
            cur.execute(
                """SELECT id, user_id, items, total_amount, status, special_instructions, created_at, updated_at
                   FROM orders WHERE user_id = %s
                   ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (user_id, limit, skip),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) as total FROM orders WHERE user_id = %s",
                (user_id,),
            )
        else:
            cur.execute(
                """SELECT id, user_id, items, total_amount, status, special_instructions, created_at, updated_at
                   FROM orders
                   ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                (limit, skip),
            )
            rows = cur.fetchall()
            cur.execute("SELECT COUNT(*) as total FROM orders")

        total = cur.fetchone()["total"]

    orders = [
        OrderResponse(
            id=row["id"],
            user_id=row["user_id"],
            items=row["items"],
            total_amount=float(row["total_amount"]),
            status=row["status"],
            special_instructions=row["special_instructions"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    return orders, total


def update_order_status(order_id: int, status_data: OrderStatusUpdate, user_id: Optional[int] = None) -> OrderResponse:
    """Update an order's status."""
    with get_db_cursor(auto_commit=True) as cur:
        if user_id:
            cur.execute(
                """UPDATE orders SET status = %s, updated_at = NOW()
                   WHERE id = %s AND user_id = %s
                   RETURNING id, user_id, items, total_amount, status, special_instructions, created_at, updated_at""",
                (status_data.status, order_id, user_id),
            )
        else:
            cur.execute(
                """UPDATE orders SET status = %s, updated_at = NOW()
                   WHERE id = %s
                   RETURNING id, user_id, items, total_amount, status, special_instructions, created_at, updated_at""",
                (status_data.status, order_id),
            )
        order = cur.fetchone()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return OrderResponse(
        id=order["id"],
        user_id=order["user_id"],
        items=order["items"],
        total_amount=float(order["total_amount"]),
        status=order["status"],
        special_instructions=order["special_instructions"],
        created_at=order["created_at"],
        updated_at=order["updated_at"],
    )


def delete_order(order_id: int, user_id: Optional[int] = None):
    """Delete/cancel an order."""
    with get_db_cursor(auto_commit=True) as cur:
        if user_id:
            cur.execute(
                "DELETE FROM orders WHERE id = %s AND user_id = %s RETURNING id",
                (order_id, user_id),
            )
        else:
            cur.execute(
                "DELETE FROM orders WHERE id = %s RETURNING id",
                (order_id,),
            )
        result = cur.fetchone()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return {"message": "Order cancelled successfully"}


def generate_bill(order_id: int) -> BillResponse:
    """Generate a bill for an order."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id, items, total_amount, status
               FROM orders WHERE id = %s""",
            (order_id,),
        )
        order = cur.fetchone()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    items = order["items"]
    subtotal = float(order["total_amount"])
    tax_rate = 0.08
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)

    return BillResponse(
        order_id=order["id"],
        items=items,
        subtotal=subtotal,
        tax=tax,
        total=total,
        status=order["status"],
        generated_at=datetime.now(timezone.utc),
    )