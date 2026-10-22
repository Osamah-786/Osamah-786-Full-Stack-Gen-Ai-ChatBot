from uuid import UUID

from app.retrieval.fusion import reciprocal_rank_fusion


def test_rrf_fuses_rankings_and_counts_a_chunk_once_per_ranking() -> None:
    first, second, third = (UUID(int=value) for value in (1, 2, 3))

    fused = reciprocal_rank_fusion(
        [[first, second, first], [second, third]],
    )

    assert [hit.chunk_id for hit in fused] == [second, first, third]
    assert fused[0].score == 1 / 61 + 1 / 62
    assert fused[1].score == 1 / 61


def test_rrf_is_deterministic_for_equal_scores() -> None:
    earlier, later = (UUID(int=value) for value in (1, 2))

    assert [hit.chunk_id for hit in reciprocal_rank_fusion([[later], [earlier]])] == [
        earlier,
        later,
    ]
