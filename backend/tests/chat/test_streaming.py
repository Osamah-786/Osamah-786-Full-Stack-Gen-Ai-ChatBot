import json

from app.chat.streaming import assistant_ui_message, stream_events


def test_stream_framing_includes_citations_and_done():
    events = list(stream_events("assistant-1", "Supported answer. [1]", [{"citation_index": 1}]))
    payloads = [json.loads(event.removeprefix("data: ").strip()) for event in events[:-1]]
    assert [payload["type"] for payload in payloads] == [
        "start", "start-step", "text-start", "text-delta", "text-end",
        "data-citations", "finish-step", "finish",
    ]
    assert payloads[5]["data"] == [{"citation_index": 1}]
    assert events[-1] == "data: [DONE]\n\n"


def test_assistant_message_persists_text_and_citations_in_ui_parts():
    message = assistant_ui_message("assistant-1", "Answer. [1]", [{"citation_index": 1}])
    assert message["parts"] == [
        {"type": "text", "text": "Answer. [1]"},
        {"type": "data-citations", "data": [{"citation_index": 1}]},
    ]
