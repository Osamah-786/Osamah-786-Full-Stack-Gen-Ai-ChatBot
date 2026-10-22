"""AI SDK UI message stream framing for a validated chat turn."""

import json
from collections.abc import Iterator


def _event(payload: dict) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def assistant_ui_message(message_id: str, answer: str, citations: list[dict]) -> dict:
    parts = [{"type": "text", "text": answer}]
    if citations:
        parts.append({"type": "data-citations", "data": citations})
    return {"id": message_id, "role": "assistant", "parts": parts}


def stream_events(message_id: str, answer: str, citations: list[dict]) -> Iterator[str]:
    yield _event({"type": "start", "messageId": message_id})
    yield _event({"type": "start-step"})
    yield _event({"type": "text-start", "id": message_id})
    for start in range(0, len(answer), 80):
        yield _event({"type": "text-delta", "id": message_id, "delta": answer[start : start + 80]})
    yield _event({"type": "text-end", "id": message_id})
    if citations:
        yield _event({"type": "data-citations", "data": citations})
    yield _event({"type": "finish-step"})
    yield _event({"type": "finish"})
    yield "data: [DONE]\n\n"
