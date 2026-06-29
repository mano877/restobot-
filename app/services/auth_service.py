from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.database.postgres import get_db_cursor
from app.middleware.auth_middleware import create_access_token
from app.models.schemas import UserRegister, UserLogin, TokenResponse, UserResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def register_user(user_data: UserRegister) -> UserResponse:
    """Register a new user — no token generated."""
    with get_db_cursor(auto_commit=True) as cur:
        # Check if username already exists
        cur.execute(
            "SELECT id FROM users WHERE username = %s OR email = %s",
            (user_data.username, user_data.email),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or email already exists",
            )

        hashed_pw = hash_password(user_data.password)
        cur.execute(
            """INSERT INTO users (username, email, hashed_password, full_name)
               VALUES (%s, %s, %s, %s)
               RETURNING id, username, email, full_name, created_at""",
            (
                user_data.username,
                user_data.email,
                hashed_pw,
                user_data.full_name,
            ),
        )
        user = cur.fetchone()

    return UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        full_name=user["full_name"],
        created_at=user["created_at"],
    )


def login_user(login_data: UserLogin) -> TokenResponse:
    """Authenticate user and return JWT token."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, username, email, full_name, hashed_password, created_at "
            "FROM users WHERE username = %s",
            (login_data.username,),
        )
        user = cur.fetchone()

    if not user or not verify_password(login_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user["id"], user["username"])
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            created_at=user["created_at"],
        ),
    )
