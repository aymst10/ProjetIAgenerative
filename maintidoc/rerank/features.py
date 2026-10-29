"""BM25 et traits lexicaux pour le reranker, sans modèle lourd."""

from __future__ import annotations

import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9àâäéèêëïîôùûüç]+", re.IGNORECASE)
STOP = {
    "les", "des", "une", "dans", "pour", "par", "sur", "avec", "sans", "comme",
    "cette", "cet", "elle", "ils", "elles", "pas", "plus", "tout", "tous",
    "toute", "toutes", "qui", "que", "est", "sont", "aux", "son", "ses", "leur",
    "leurs", "entre", "avant", "apres", "après", "sous", "chez", "du", "au",
}


def tokens(text: str) -> list[str]:
    words = [match.group(0).lower() for match in TOKEN.finditer(text)]
    return [word for word in words if word not in STOP and len(word) > 2]


def bm25_scores(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    tokenized = [tokens(document) for document in documents]
    query_tokens = tokens(query)
    avgdl = sum(len(item) for item in tokenized) / max(len(tokenized), 1)
    df: Counter[str] = Counter()
    for item in tokenized:
        df.update(set(item))
    scores: list[float] = []
    total = max(len(tokenized), 1)
    for item in tokenized:
        counts = Counter(item)
        length = len(item) or 1
        score = 0.0
        for term in query_tokens:
            if term not in counts:
                continue
            idf = math.log(1 + (total - df[term] + 0.5) / (df[term] + 0.5))
            freq = counts[term]
            denom = freq + k1 * (1 - b + b * length / (avgdl or 1))
            score += idf * (freq * (k1 + 1)) / (denom or 1)
        scores.append(score)
    return scores
