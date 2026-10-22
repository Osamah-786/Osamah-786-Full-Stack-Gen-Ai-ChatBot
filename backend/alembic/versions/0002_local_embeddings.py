"""Add a separate vector column for local MiniLM embeddings."""

from typing import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "0002_local_embeddings"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    column_type = op.get_bind().execute(
        sa.text("""
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class t ON t.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public' AND t.relname = 'document_chunks'
              AND a.attname = 'embedding' AND NOT a.attisdropped
        """)
    ).scalar_one_or_none()
    if column_type != "vector(1536)":
        raise RuntimeError(
            "Expected public.document_chunks.embedding to be vector(1536); "
            f"found {column_type!r}. No schema changes were applied."
        )

    op.add_column(
        "document_chunks",
        sa.Column("embedding_384", pgvector.sqlalchemy.Vector(dim=384), nullable=True),
    )
    op.create_index(
        "ix_document_chunks_embedding_384_hnsw",
        "document_chunks",
        ["embedding_384"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding_384": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_embedding_384_hnsw", table_name="document_chunks")
    op.drop_column("document_chunks", "embedding_384")
