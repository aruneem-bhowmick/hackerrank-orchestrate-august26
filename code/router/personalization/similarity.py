"""Deterministic lexical similarity used by receiver-scoped retrieval."""

import math
import re
from collections import Counter
from collections.abc import Sequence

_TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")


def tokenize(text: object) -> list[str]:
    """Return stable lowercase alphanumeric tokens for one text value."""
    return _TOKEN_PATTERN.findall(text.lower()) if isinstance(text, str) else []


def tfidf_cosine_similarity(query: str, documents: Sequence[str]) -> list[float]:
    """Return per-document TF-IDF cosine scores fit solely to these inputs."""
    query_tokens = tokenize(query)
    document_tokens = [tokenize(document) for document in documents]
    if not query_tokens:
        return [0.0] * len(documents)
    corpus = [query_tokens, *document_tokens]
    document_frequency = Counter(token for row in corpus for token in set(row))
    count = len(corpus)
    idf = {token: math.log((1 + count) / (1 + frequency)) + 1 for token, frequency in document_frequency.items()}
    query_vector = _tfidf_vector(query_tokens, idf)
    return [_cosine(query_vector, _tfidf_vector(tokens, idf)) for tokens in document_tokens]


def _tfidf_vector(tokens: Sequence[str], idf: dict[str, float]) -> dict[str, float]:
    """Build a term-frequency times inverse-document-frequency vector."""
    if not tokens:
        return {}
    frequencies = Counter(tokens)
    total = len(tokens)
    return {token: (frequency / total) * idf[token] for token, frequency in frequencies.items()}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    """Compute a rounded, zero-safe cosine similarity for sparse vectors."""
    if not left or not right:
        return 0.0
    numerator = sum(value * right.get(token, 0.0) for token, value in left.items())
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(sum(value * value for value in right.values()))
    return round(numerator / denominator, 6) if denominator else 0.0
