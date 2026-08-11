"""Original RepoNPC P2 fixture source; it is not production retrieval code."""

from __future__ import annotations


def rank_evidence(lexical_ids: list[str], vector_ids: list[str]) -> list[str]:
    """Return a stable fixture ordering with duplicate evidence IDs removed."""
    return list(dict.fromkeys([*lexical_ids, *vector_ids]))


class CitationResolver:
    """Resolve a fixture evidence ID to an immutable-looking local reference."""

    def resolve(self, evidence_id: str) -> str:
        return f"fixture://evidence/{evidence_id}"


def delimit_untrusted_evidence(text: str) -> str:
    """Mark repository text as data so fixture prompt injections have no authority."""
    return f"<evidence>{text}</evidence>"
