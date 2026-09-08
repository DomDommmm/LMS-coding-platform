
from typing import List
import jwt
from fastapi import Depends, HTTPException, Header
from jwt import InvalidTokenError
import json
from typing import TypedDict
from src.jwk_service import PublicKeyService
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

RS_ALGORITHM = "RS256"
ALGROTHM = "HS256"


class UserPayload(TypedDict):
    """Typed view of the JWT payload returned by get_current_user.

    Extra standard JWT claims (iat, exp, etc.) may be present in the dict
    but are not part of this interface — business code must not rely on them.
    """
    sub: int
    email: str
    roles: list[str]


def credential_exception(msg: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=msg,
        headers={"WWW-Authenticate": "Bearer"},
    )


security = HTTPBearer()


async def get_current_user(
    crendential: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserPayload:
    if not crendential:
        raise credential_exception("Authorization Header is missing")
    token: str = crendential.credentials

    if not token:
        raise credential_exception("Invalid authorization header format")
    public_key = PublicKeyService.get()
    try:
        payload = jwt.decode(token, public_key, algorithms=RS_ALGORITHM)
        # payload format: {"sub": str(client_id), "email": email, "roles": roles}
        sub = payload.get("sub", None)
        email = payload.get("email")
        raw_roles = payload.get("roles")
        if not sub or not isinstance(sub, str) or not isinstance(email, str) or not isinstance(raw_roles, list):
            raise credential_exception("Invalid authorization token body")
        user_id = int(sub)
        roles: list[str] = []
        for role in raw_roles:
            if not isinstance(role, str):
                raise credential_exception("Invalid authorization token body")
            roles.append(role)
        return {
            "sub": user_id,
            "email": email,
            "roles": roles,
        }
    except (InvalidTokenError, TypeError, ValueError):
        raise credential_exception("Could not validate credentials")
