"""Reject answers whose citations are not supported by retrieved passages."""

import re

from app.assistant.outputs import GroundedAnswer


class GroundingError(ValueError):
    """The model returned unsupported or malformed evidence."""


_MARKER = re.compile(r"\[(\d+)\]")


def validate_answer(
    result: GroundedAnswer,
    passages: dict,
) -> GroundedAnswer:
    answer = result.answer.strip()
    if not answer:
        raise GroundingError("The answer is empty")
    indices = [citation.citation_index for citation in result.citations]
    chunk_ids = [citation.chunk_id for citation in result.citations]
    if len(set(indices)) != len(indices) or len(set(chunk_ids)) != len(chunk_ids):
        raise GroundingError("Citations must have unique indices and passages")

    markers = [int(value) for value in _MARKER.findall(answer)]
    if result.insufficient_evidence:
        explicit = re.search(
            r"not enough evidence|(?:does|do) not provide enough evidence|insufficient evidence",
            answer,
            re.IGNORECASE,
        )
        if result.citations or markers or explicit is None:
            raise GroundingError("Insufficient-evidence answers must be explicit and uncited")
        return result.model_copy(update={"answer": answer})

    if not result.citations or set(markers) != set(indices):
        raise GroundingError("Every grounded answer needs matching citation markers")
    if any(not paragraph.strip() or not _MARKER.search(paragraph) for paragraph in answer.split("\n") if paragraph.strip()):
        raise GroundingError("Each answer paragraph must include a citation")

    for citation in result.citations:
        passage = passages.get(citation.chunk_id)
        if passage is None:
            raise GroundingError("Citation references an unavailable passage")
        if not _contains_normalized(passage.text, citation.excerpt):
            raise GroundingError("Citation excerpt is not present in its passage")
    return result.model_copy(update={"answer": answer})


def trusted_citations(
    result: GroundedAnswer,
    passages: dict,
) -> list[dict]:
    return [
        {
            "citation_index": citation.citation_index,
            "document_chunk_id": str(citation.chunk_id),
            "excerpt": citation.excerpt,
            "ticker": passages[citation.chunk_id].ticker,
            "company_name": passages[citation.chunk_id].company_name,
            "filing_type": passages[citation.chunk_id].filing_type,
            "filing_date": passages[citation.chunk_id].filing_date.isoformat(),
            "page_number": passages[citation.chunk_id].page_number,
            "section": passages[citation.chunk_id].section,
            "source_url": passages[citation.chunk_id].source_url,
        }
        for citation in result.citations
    ]


def _contains_normalized(passage: str, excerpt: str) -> bool:
    def normalize(value: str) -> str:
        return " ".join(value.split())

    return bool(excerpt.strip()) and normalize(excerpt) in normalize(passage)
