"""Evidence Bundle types and safe output serialization."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RetrievalResult:
    """The qualifying historical records and their deterministic relevance."""

    evidence_ids: tuple[str, ...]
    evidence_basis: str
    mean_relevance: float


@dataclass(frozen=True)
class EvidenceBundle:
    """One incoming message's retrieved history and personalization inputs."""

    message_id: str
    evidence_ids: tuple[str, ...]
    evidence_basis: str
    retrieval_method: str
    personalization_signals: Mapping[str, object]

    def __post_init__(self) -> None:
        """Normalize evidence ids to the immutable contract representation."""
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids))


def no_evidence_result() -> RetrievalResult:
    """Create the single canonical result for a genuine retrieval miss."""
    return RetrievalResult((), "no relevant historical evidence", 0.0)


def evidence_ids_for_output(bundle: EvidenceBundle) -> str:
    """Return comma-separated evidence ids or the required `none` sentinel."""
    return ",".join(bundle.evidence_ids) if bundle.evidence_ids else "none"
