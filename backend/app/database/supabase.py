"""Supabase clients for user-scoped and trusted backend operations."""

from functools import lru_cache

from supabase import Client, ClientOptions, create_client

from app.config import settings


def get_user_client(access_token: str) -> Client:
    """Create a Supabase client whose requests run with the user's JWT and RLS."""
    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key.get_secret_value(),
        options=ClientOptions(
            headers={"Authorization": f"Bearer {access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


@lru_cache(maxsize=1)
def get_service_role_client() -> Client:
    """Return the backend-only service-role client for trusted operations."""
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key.get_secret_value(),
    )
