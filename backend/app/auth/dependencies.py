"""FastAPI dependencies for Supabase-authenticated requests."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client
from supabase import AuthApiError
from supabase_auth import User

from app.database.supabase import get_user_client

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = get_user_client(credentials.credentials).auth.get_user(
            credentials.credentials
        )
    except AuthApiError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if response is None or response.user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return response.user


def get_authenticated_client(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Client:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return get_user_client(credentials.credentials)
