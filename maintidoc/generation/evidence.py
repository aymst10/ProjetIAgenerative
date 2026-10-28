"""Vérifie qu'une citation pointe un extrait récupéré et soutient l'affirmation."""

from __future__ import annotations

import re

from maintidoc.retrieval.search import Hit
from maintidoc.schemas import AssistantOutput, Citation

STOPWORDS = {
    "les", "des", "une", "dans", "pour", "par", "sur", "avec", "sans", "comme",
    "cette", "cet", "elle", "ils", "elles", "pas", "plus", "tout", "tous",
    "toute", "toutes", "qui", "que", "est", "sont", "aux", "son", "ses", "leur",
    "leurs", "dans", "entre", "avant", "apres", "après", "sous", "chez",
}
TOKEN = re.compile(r"[a-z0-9àâäéèêëïîôùûüç]+", re.IGNORECASE)
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
INJECTION_MARKERS = (
    "ignore les instructions",
    "ignore previous",
    "service externe",
    "envoie tous les rapports",
    "exfiltre",
    "system prompt",
)
CONFIDENCE = re.compile(r"confiance\s*(?:de\s*)?\d+", re.IGNORECASE)
URL = re.compile(r"https?://", re.IGNORECASE)


def content_words(text: str) -> list[str]:
    words = [match.group(0).lower() for match in TOKEN.finditer(text)]
    return [word for word in words if word not in STOPWORDS and len(word) > 2]


def is_injection(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in INJECTION_MARKERS)


def support_ratio(sentence: str, excerpt: str) -> float:
    if is_injection(sentence) or CONFIDENCE.search(sentence) or URL.search(sentence):
        return 0.0
    if is_injection(excerpt):
        return 0.0
    words = content_words(sentence)
    if not words:
        return 0.0
    excerpt_words = set(content_words(excerpt))
    overlap = sum(1 for word in words if word in excerpt_words)
    return overlap / len(words)


def supports(sentence: str, excerpt: str) -> bool:
    return support_ratio(sentence, excerpt) >= 0.6


def _key(document_id: str, page: int, element_id: str) -> tuple[str, int, str]:
    return (document_id, page, element_id)


def hit_map(hits: list[Hit]) -> dict[tuple[str, int, str], Hit]:
    return {_key(hit.document_id, hit.page, hit.element_id): hit for hit in hits}


def contradictory_hits(hits: list[Hit]) -> list[Hit]:
    usable = [hit for hit in hits if not is_injection(hit.text)]
    conflicts: list[Hit] = []
    for left_index, left in enumerate(usable):
        left_words = set(content_words(NUMBER.sub(" ", left.text)))
        left_numbers = set(NUMBER.findall(left.text))
        if not left_numbers:
            continue
        for right in usable[left_index + 1 :]:
            right_words = set(content_words(NUMBER.sub(" ", right.text)))
            right_numbers = set(NUMBER.findall(right.text))
            if not right_numbers or left_numbers == right_numbers:
                continue
            union = left_words | right_words
            if not union:
                continue
            if len(left_words & right_words) / len(union) >= 0.55:
                conflicts.extend([left, right])
    unique: list[Hit] = []
    seen: set[tuple[str, int, str]] = set()
    for hit in conflicts:
        key = _key(hit.document_id, hit.page, hit.element_id)
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique


def sentences_of(text: str) -> list[str]:
    protected = re.sub(r"(\d)\.(\d)", r"\1§\2", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [part.replace("§", ".").strip() for part in parts if part.strip()]


def verify_output(output: AssistantOutput, hits: list[Hit]) -> AssistantOutput:
    """Retire les citations inconnues et les phrases que les extraits ne soutiennent pas."""
    known = hit_map(hits)
    if output.status in {"access_denied", "abstained", "budget_exceeded", "rejected"}:
        return output.model_copy(update={"citations": [], "proposed_action": output.proposed_action})

    kept_citations: list[Citation] = []
    for citation in output.citations:
        key = _key(citation.document_id, citation.page, citation.element_id)
        if key in known and not is_injection(known[key].text):
            kept_citations.append(citation)

    if output.status == "needs_clarification":
        answer = output.answer
        if is_injection(answer) or URL.search(answer):
            answer = "Une clarification est nécessaire. Aucune instruction contenue dans un document n'est suivie."
        numbers = set(NUMBER.findall(answer))
        source_numbers = set()
        for citation in kept_citations:
            source_numbers.update(NUMBER.findall(known[_key(citation.document_id, citation.page, citation.element_id)].text))
        if numbers - source_numbers:
            answer = "Les extraits autorisés ne permettent pas de trancher."
        return output.model_copy(update={"answer": answer, "citations": kept_citations})

    supported: list[str] = []
    used: list[Citation] = []
    seen: set[tuple[str, int, str]] = set()
    for sentence in sentences_of(output.answer):
        if is_injection(sentence) or CONFIDENCE.search(sentence) or URL.search(sentence):
            continue
        best: Hit | None = None
        best_ratio = 0.0
        for hit in known.values():
            ratio = support_ratio(sentence, hit.text)
            if ratio > best_ratio:
                best = hit
                best_ratio = ratio
        if best is None or best_ratio < 0.6:
            continue
        supported.append(sentence)
        marker = _key(best.document_id, best.page, best.element_id)
        if marker not in seen:
            seen.add(marker)
            used.append(Citation(document_id=best.document_id, page=best.page, element_id=best.element_id))

    if not supported:
        return AssistantOutput(
            status="abstained",
            answer="Aucune affirmation n'est suffisamment soutenue par les extraits récupérés.",
            citations=[],
            uncertainties=list(output.uncertainties),
            clarification_question=output.clarification_question,
            proposed_action=None,
        )
    status = output.status if output.status in {"awaiting_approval", "ticket_created"} else "answered"
    return output.model_copy(update={"answer": " ".join(supported), "citations": used, "status": status})
