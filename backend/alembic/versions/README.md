# Alembic revisions

| Revision | Schema change |
| --- | --- |
| `0001_initial.py` (`0001_initial`) | Creates vector extension, user/source/chunk/chat/citation tables, initial 1536-vector and generated FTS columns/indexes, RLS and policies. |
| `0002_local_embeddings.py` (`0002_local_embeddings`) | Verifies the legacy `embedding` is `vector(1536)`, then adds `embedding_384 vector(384)` and its HNSW cosine index without removing old data. |

Alembic orders these via `down_revision`; `env.py` loads SQLAlchemy metadata. Future revisions should be additive and reviewed for data preservation, vector-model compatibility, RLS, and index behavior before they are applied.
