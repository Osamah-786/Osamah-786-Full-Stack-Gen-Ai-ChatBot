from app import embeddings
import pytest


class FakeModel:
    def __init__(self) -> None:
        self.calls = []

    def encode(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        return [[0.1] * embeddings.DIMENSIONS for _ in texts]


def test_document_and_query_embeddings_share_model_and_dimensions(monkeypatch) -> None:
    model = FakeModel()
    monkeypatch.setattr(embeddings, "_load_model", lambda: model)

    documents = embeddings.embed_documents(["filing chunk", "another chunk"])
    query = embeddings.embed_query("revenue query")

    assert len(documents) == 2
    assert all(len(vector) == embeddings.DIMENSIONS for vector in documents)
    assert len(query) == embeddings.DIMENSIONS
    assert model.calls[0][1]["normalize_embeddings"] is True
    assert model.calls[1][0] == ["revenue query"]


def test_embed_documents_rejects_unexpected_dimensions(monkeypatch) -> None:
    class WrongDimensionModel:
        def encode(self, texts, **kwargs):
            return [[0.0] * 3 for _ in texts]

    monkeypatch.setattr(embeddings, "_load_model", lambda: WrongDimensionModel())

    with pytest.raises(RuntimeError, match="384-dimensional"):
        embeddings.embed_documents(["text"])
