from typing import Annotated

from fastapi import Depends, HTTPException, Request
from jose import JWTError

from auth.auth import decode_jwt
from booking.models import Permission, TokenPayload, UserRole, has_permission
from web.config import get_settings


def get_current_user(request: Request) -> TokenPayload:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    try:
        payload = decode_jwt(token, get_settings())
    except JWTError:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    # Token nach Rollenänderung / Passwort-Reset ungültig?
    invalidations = getattr(request.app.state, "token_invalidations", {})
    if payload.iat < invalidations.get(payload.sub, 0):
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    # Erzwungener Passwortwechsel: nur /change-password und /logout erlaubt
    if payload.must_change_password:
        path = request.url.path
        if path not in ("/change-password", "/logout"):
            raise HTTPException(status_code=302, headers={"Location": "/change-password"})
    return payload


def require_role(*roles: UserRole):
    def checker(user: Annotated[TokenPayload, Depends(get_current_user)]) -> TokenPayload:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
        return user
    return checker


def require_permission(permission: Permission):
    def checker(user: Annotated[TokenPayload, Depends(get_current_user)]) -> TokenPayload:
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=403, detail="Keine Berechtigung")
        return user
    return checker


CurrentUser = Annotated[TokenPayload, Depends(get_current_user)]
