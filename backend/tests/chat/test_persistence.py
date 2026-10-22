from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.database import chats
from app.database.models import ChatMessage, MessageCitation


def test_persist_turn_links_citations_and_checks_thread_owner(monkeypatch):
    thread_id = UUID(int=1)
    chunk_id = UUID(int=2)
    captured = []

    class FakeSession:
        def get(self, model, _id):
            assert model.__name__ == "ChatThread"
            return SimpleNamespace(user_id=UUID(int=3), title=None, updated_at=None)

        def add_all(self, rows):
            captured.extend(rows)
            for row in rows:
                if isinstance(row, ChatMessage):
                    row.id = uuid4()

        def flush(self):
            pass

    @contextmanager
    def begin():
        yield FakeSession()

    monkeypatch.setattr(chats, "get_session_factory", lambda: SimpleNamespace(begin=begin))
    chats.persist_turn(
        thread_id,
        str(UUID(int=3)),
        {"id": "user-msg", "role": "user", "parts": []},
        {"id": "assistant-msg", "role": "assistant", "parts": []},
        "Question",
        [{"document_chunk_id": chunk_id, "citation_index": 1, "excerpt": "exact quote"}],
    )
    citation = next(row for row in captured if isinstance(row, MessageCitation))
    assistant = next(row for row in captured if isinstance(row, ChatMessage) and row.role == "assistant")
    assert citation.message_id == assistant.id
    assert citation.document_chunk_id == chunk_id
