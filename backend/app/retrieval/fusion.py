"""Rank-based fusion for independent retrieval result lists."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FusedHit:
    chunk_id: UUID
    score: float


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[UUID]],
    *,
    k: int = 60,
) -> list[FusedHit]:
    """Fuse ranked chunk IDs without comparing vector and text-search scores."""
    if k < 0:
        raise ValueError("RRF constant must be non-negative")

    scores: dict[UUID, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(dict.fromkeys(ranking), start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return [
        FusedHit(chunk_id, score)
        for chunk_id, score in sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
    ]
