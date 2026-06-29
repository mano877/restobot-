from fastapi import APIRouter, Depends, Query

from app.middleware.auth_middleware import get_current_user, get_current_user_id
from app.models.schemas import (
    OrderCreate,
    OrderResponse,
    OrderListResponse,
    OrderStatusUpdate,
    BillResponse,
)
from app.services.order_service import (
    create_order,
    get_order,
    list_orders,
    update_order_status,
    delete_order,
    generate_bill,
)

router = APIRouter(prefix="/orders", tags=["Orders"])

user_orders_router = APIRouter(prefix="/users", tags=["Orders"])


@router.post(
    "",
    response_model=OrderResponse,
    status_code=201,
    summary="Create a new order",
)
def create_order_endpoint(
    order_data: OrderCreate,
    current_user=Depends(get_current_user),
):
    """Place a new order with menu items."""
    return create_order(user_id=current_user.user_id, order_data=order_data)


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List current user's orders",
)
def list_orders_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user_id),
):
    """Get a list of orders for the currently authenticated user."""
    orders, total = list_orders(user_id=current_user, skip=skip, limit=limit)
    return OrderListResponse(orders=orders, total=total)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
)
def get_order_endpoint(
    order_id: int,
    current_user=Depends(get_current_user_id),
):
    """Get details of a specific order (only own orders)."""
    return get_order(order_id=order_id, user_id=current_user)


@user_orders_router.get(
    "/{user_id}/orders",
    response_model=OrderListResponse,
    summary="Get orders for a specific user",
)
def get_user_orders_endpoint(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(get_current_user),
):
    """Retrieve all orders placed by a specific user."""
    # Users can only see their own orders unless admin (simplified: match user_id)
    if current_user.user_id != user_id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own orders",
        )

    orders, total = list_orders(user_id=user_id, skip=skip, limit=limit)
    return OrderListResponse(orders=orders, total=total)


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order status",
)
def update_order_status_endpoint(
    order_id: int,
    status_data: OrderStatusUpdate,
    current_user=Depends(get_current_user_id),
):
    """Update the status of an order (pending → confirmed → preparing → ready → delivered → cancelled)."""
    return update_order_status(order_id=order_id, user_id=current_user, status_data=status_data)


@router.delete(
    "/{order_id}",
    summary="Delete an order",
)
def delete_order_endpoint(
    order_id: int,
    current_user=Depends(get_current_user_id),
):
    """Delete an order (only own orders)."""
    return delete_order(order_id=order_id, user_id=current_user)


@router.get(
    "/{order_id}/bill",
    response_model=BillResponse,
    summary="Generate bill for an order",
)
def get_bill_endpoint(
    order_id: int,
    current_user=Depends(get_current_user_id),
):
    """Generate a detailed bill for an order including subtotal, tax, and total."""
    return generate_bill(order_id=order_id)
