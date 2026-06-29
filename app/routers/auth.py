from fastapi import APIRouter

from app.models.schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from app.services.auth_service import register_user, login_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    summary="Register a new user",
)
def register(user_data: UserRegister):
    """Register a new user account."""
    return register_user(user_data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get JWT token",
)
def login(login_data: UserLogin):
    """Authenticate with username/password and receive a JWT token."""
    return login_user(login_data)
