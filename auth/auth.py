from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from booking.models import TokenPayload, UserRole
from web.config import Settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.strip().encode())


def create_jwt(
    user_id: str,
    username: str,
    role: UserRole,
    settings: Settings,
    mannschaft: Optional[str] = None,
    must_change_password: bool = False,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if mannschaft:
        payload["mannschaft"] = mannschaft
    if must_change_password:
        payload["must_change_password"] = True
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str, settings: Settings) -> TokenPayload:
    data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return TokenPayload(
        sub=data["sub"],
        username=data["username"],
        role=UserRole(data["role"]),
        mannschaft=data.get("mannschaft"),
        must_change_password=data.get("must_change_password", False),
        exp=data["exp"],
        iat=data.get("iat", 0),
    )
