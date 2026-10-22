"""Supabase persistence for chat threads and messages."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from supabase import Client

from app.database.supabase import get_service_role_client
from app.database.models import ChatMessage, ChatThread, MessageCitation
from app.database.session import get_session_factory


def list_threads(client: Client) -> list[dict]:
    response = (
        client.table("chat_threads")
        .select("*")
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data


def create_thread(client: Client, user_id: str, email: str | None) -> dict:
    if email is None:
        raise HTTPException(status_code=400, detail="An email address is required")
    client.table("users").upsert({"id": user_id, "email": email}).execute()
    response = (
        client.table("chat_threads")
        .insert({"user_id": user_id, "title": None})
        .execute()
    )
    return response.data[0]


def get_thread_access(thread_id: UUID, user_id: str) -> dict:
    response = (
        get_service_role_client()
        .table("chat_threads")
        .select("id,user_id")
        .eq("id", str(thread_id))
        .maybe_single()
        .execute()
    )
    thread = response.data
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    if thread["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return thread


def load_messages(client: Client, thread_id: UUID) -> list[dict]:
    response = (
        client.table("chat_messages")
        .select("id,role,content,created_at")
        .eq("thread_id", str(thread_id))
        .order("created_at")
        .execute()
    )
    return [message["content"] | {"createdAt": message["created_at"]} for message in response.data]


def persist_turn(
    thread_id: UUID,
    user_id: str,
    user_message: dict,
    assistant_message: dict,
    title: str,
    citations: list[dict],
) -> UUID:
    with get_session_factory().begin() as session:
        thread = session.get(ChatThread, thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found")
        if str(thread.user_id) != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        assistant_row = ChatMessage(
            thread_id=thread_id, role="assistant", content=assistant_message
        )
        session.add_all(
            [
                ChatMessage(thread_id=thread_id, role="user", content=user_message),
                assistant_row,
            ]
        )
        session.flush()
        session.add_all(
            [
                MessageCitation(
                    message_id=assistant_row.id,
                    document_chunk_id=UUID(str(citation["document_chunk_id"])),
                    citation_index=citation["citation_index"],
                    excerpt=citation["excerpt"],
                )
                for citation in citations
            ]
        )
        thread.title = title[:300]
        thread.updated_at = datetime.now(timezone.utc)
        return assistant_row.id
