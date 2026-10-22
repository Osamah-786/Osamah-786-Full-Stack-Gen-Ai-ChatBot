"""Chat thread and streaming endpoints."""

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import StreamingResponse
from supabase import Client
from supabase_auth import User

from app.auth.dependencies import get_authenticated_client, get_current_user
from app.database.chats import (
    create_thread,
    get_thread_access,
    list_threads,
    load_messages,
    persist_turn,
)
from app.chat.orchestrator import prepare_turn
from app.chat.streaming import assistant_ui_message, stream_events
from app.grounding.validator import GroundingError

router = APIRouter(prefix="/chat", tags=["chat"])


class UIMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    role: str
    parts: list[dict[str, object]] = Field(default_factory=list)


class StreamRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thread_id: UUID = Field(alias="threadId")
    messages: list[UIMessage]


@router.get("/threads")
async def get_threads(
    user: User = Depends(get_current_user),
    client: Client = Depends(get_authenticated_client),
) -> list[dict]:
    return await asyncio.to_thread(list_threads, client)


@router.post("/threads", status_code=201)
async def post_thread(
    user: User = Depends(get_current_user),
    client: Client = Depends(get_authenticated_client),
) -> dict:
    return await asyncio.to_thread(create_thread, client, user.id, user.email)


@router.get("/threads/{thread_id}/messages")
async def get_messages(
    thread_id: UUID,
    user: User = Depends(get_current_user),
    client: Client = Depends(get_authenticated_client),
) -> list[dict]:
    await asyncio.to_thread(get_thread_access, thread_id, user.id)
    return await asyncio.to_thread(load_messages, client, thread_id)


@router.post("/stream")
async def stream_chat(
    request: StreamRequest,
    user: User = Depends(get_current_user),
    client: Client = Depends(get_authenticated_client),
) -> StreamingResponse:
    await asyncio.to_thread(get_thread_access, request.thread_id, user.id)
    last_message = next(
        (message for message in reversed(request.messages) if message.role == "user"),
        None,
    )
    if last_message is None:
        raise HTTPException(status_code=422, detail="A user message is required")

    text = "".join(
        str(part.get("text", ""))
        for part in last_message.parts
        if part.get("type") == "text"
    ).strip()
    if not text:
        raise HTTPException(status_code=422, detail="User message must contain text")

    assistant_id = str(uuid4())
    try:
        prepared = await asyncio.to_thread(
            prepare_turn, text, str(user.id), request.thread_id
        )
    except GroundingError as exc:
        raise HTTPException(status_code=502, detail="Unable to verify answer grounding") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Document retrieval is temporarily unavailable") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to generate a grounded answer") from exc

    answer = prepared.result.answer
    assistant_message = assistant_ui_message(assistant_id, answer, prepared.citations)

    async def events() -> AsyncIterator[str]:
        for event in stream_events(assistant_id, answer, prepared.citations):
            if '"type":"finish"' in event or event == "data: [DONE]\n\n":
                continue
            yield event
        try:
            await asyncio.to_thread(
                persist_turn,
                request.thread_id,
                str(user.id),
                last_message.model_dump(mode="json"),
                assistant_message,
                text,
                prepared.citations,
            )
        except (SQLAlchemyError, HTTPException):
            yield _event({"type": "error", "errorText": "Unable to save chat message"})
            return
        yield _event({"type": "finish"})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


def _event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
