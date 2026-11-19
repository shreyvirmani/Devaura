from typing import Optional
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel


class CurrentUser(BaseModel):
    id: str
    email: str
    name: str
    is_authenticated: bool = True


# Default developer context for local development / testing
DEV_USER = CurrentUser(
    id="usr_devaura_dev_001",
    email="dev@devaura.local",
    name="Devaura Engineer",
    is_authenticated=True,
)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> CurrentUser:
    """Authentication dependency skeleton.
    
    Accepts Bearer tokens or API keys. In development mode without credentials,
    defaults gracefully to the developer user.
    """
    if x_api_key:
        return CurrentUser(
            id=f"usr_api_{x_api_key[:8]}",
            email=f"apikey_{x_api_key[:6]}@devaura.local",
            name="API Key User",
            is_authenticated=True,
        )

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            # Validates token structure (skeleton validation)
            if len(token) > 5:
                return CurrentUser(
                    id="usr_bearer_user",
                    email="developer@devaura.io",
                    name="Authorized User",
                    is_authenticated=True,
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In development/local mode, provide default developer identity
    return DEV_USER
