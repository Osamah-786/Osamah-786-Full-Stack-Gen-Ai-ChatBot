"""Request-scoped dependencies for the document agent."""

from dataclasses import dataclass, field
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.retrieval.retriever import RetrievedPassage


@dataclass
class DocumentAgentDeps:
    user_id: str
    thread_id: UUID
    session_factory: Callable[[], Session]
    passages: dict[UUID, RetrievedPassage] = field(default_factory=dict)
