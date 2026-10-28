"""Générateur déterministe : les phrases retenues sont des extraits autorisés."""

from __future__ import annotations

from maintidoc.config import Settings, get_settings
from maintidoc.generation.evidence import (
    content_words,
    contradictory_hits,
    is_injection,
    sentences_of,
    supports,
    verify_output,
)
from maintidoc.generation.vlm import describe_with_vlm
from maintidoc.ingest.embeddings import image_signals
from maintidoc.retrieval.search import Hit
from maintidoc.schemas import AssistantOutput, Citation, ProposedAction
from maintidoc.versions import load_prompts

OUT_OF_ROLE = (
    "shunte",
    "shunter",
    "pilote la pompe",
    "piloter",
    "démarre la pompe",
    "demarre la pompe",
    "arrête la machine",
    "arrete la machine",
    "contourne la sécurité",
    "contourne la securite",
    "bypass",
)
def _overlap(question: str, text: str) -> int:
    return len(set(content_words(question)) & set(content_words(text)))


def _render_prompt(question: str, equipment_id: str | None, visual: str, excerpts: str, tools: str) -> str:
    prompts = load_prompts()
    return prompts["answer"]["user_template"].format(
        question=question,
        equipment_id=equipment_id or "non précisé",
        visual=visual or "aucune",
        excerpts=excerpts or "aucun",
        tool_results=tools or "aucun",
        schema=AssistantOutput.model_json_schema(),
    )


def _citation(hit: Hit) -> Citation:
    return Citation(document_id=hit.document_id, page=hit.page, element_id=hit.element_id)


def _select(question: str, hits: list[Hit], equipment_id: str | None) -> list[Hit]:
    pool = [hit for hit in hits if not is_injection(hit.text)]
    if equipment_id:
        focused = [hit for hit in pool if equipment_id in hit.equipment_ids or equipment_id in hit.text]
        if focused:
            pool = focused
    ranked = sorted(
        pool,
        key=lambda hit: (
            _overlap(question, hit.text),
            1 if hit.element_type in {"paragraph", "table"} else 0,
        ),
        reverse=True,
    )
    if not ranked or _overlap(question, ranked[0].text) < 2:
        return []
    chosen = [ranked[0]]
    for hit in ranked[1:]:
        same_document = hit.document_id == ranked[0].document_id
        if same_document and _overlap(question, hit.text) >= 2:
            chosen.append(hit)
            break
    return chosen


def _ticket_requested(question: str) -> bool:
    lowered = question.lower()
    return "ticket" in lowered


def compose_answer(
    question: str,
    hits: list[Hit],
    *,
    equipment_id: str | None = None,
    image_path: str | None = None,
    access_denied: bool = False,
    tool_results: str = "",
    settings: Settings | None = None,
) -> AssistantOutput:
    settings = settings or get_settings()
    visual = ""
    uncertainties: list[str] = []
    if image_path:
        signals = image_signals(image_path)
        if not signals["readable"]:
            uncertainties.append("La photographie est illisible.")
            if not equipment_id:
                return AssistantOutput(
                    status="needs_clarification",
                    answer="La photographie est illisible. L'équipement ne peut pas être identifié.",
                    uncertainties=uncertainties,
                    clarification_question="Pouvez-vous photographier de nouveau le panneau et la plaque signalétique ?",
                )
        else:
            visual = f"teinte dominante {signals['dominant_color']}"
            uncertainties.append(
                f"Observation visuelle : teinte dominante {signals['dominant_color']}. "
                "Une ressemblance visuelle ne confirme pas l'équipement ni le diagnostic."
            )
        vlm_note = describe_with_vlm(image_path, question, settings)
        if vlm_note:
            visual = vlm_note

    if access_denied:
        return AssistantOutput(
            status="access_denied",
            answer="Ce corpus ou cet équipement n'est pas autorisé pour ce compte.",
        )

    lowered = question.lower()
    if any(marker in lowered for marker in OUT_OF_ROLE):
        return AssistantOutput(
            status="abstained",
            answer="Cette demande dépasse le rôle documentaire de MaintiDoc. Aucun équipement n'est piloté.",
            uncertainties=["Hors périmètre : pas de pilotage ni de contournement de protection."],
        )

    ignored = any(is_injection(hit.text) for hit in hits)
    if ignored:
        uncertainties.append("Un passage contenant une instruction a été ignoré et traité comme une donnée.")

    usable = [hit for hit in hits if not is_injection(hit.text)]
    conflicts = contradictory_hits(usable)
    relevant_conflicts = [hit for hit in conflicts if _overlap(question, hit.text) >= 2]
    if len(relevant_conflicts) >= 2:
        drafted = AssistantOutput(
            status="needs_clarification",
            answer="Les extraits autorisés se contredisent. Aucune valeur n'est retenue.",
            citations=[_citation(hit) for hit in relevant_conflicts[:4]],
            uncertainties=uncertainties + ["Les documents cités ne concordent pas."],
            clarification_question="Quelle version du document fait foi pour cette consigne ?",
        )
        return verify_output(drafted, hits)

    if not equipment_id and "voyant" in lowered:
        meanings = {hit.text for hit in usable if "voyant orange" in hit.text.lower()}
        if len(meanings) >= 2:
            return verify_output(
                AssistantOutput(
                    status="needs_clarification",
                    answer="Le voyant orange n'a pas le même sens sur tous les équipements couverts.",
                    citations=[_citation(hit) for hit in usable if "voyant orange" in hit.text.lower()][:4],
                    uncertainties=uncertainties,
                    clarification_question="De quel équipement s'agit-il : POMPE-A, POMPE-B, COMP-A ou COMP-B ?",
                ),
                hits,
            )

    selected = _select(question, hits, equipment_id)
    excerpts = "\n".join(f"{hit.document_id} p.{hit.page} {hit.element_id}: {hit.text}" for hit in selected)
    _render_prompt(question, equipment_id, visual, excerpts, tool_results)

    if not selected:
        return AssistantOutput(
            status="abstained",
            answer="Aucune source pertinente n'est accessible pour cette demande.",
            uncertainties=uncertainties,
        )

    sentences: list[str] = []
    citations: list[Citation] = []
    for hit in selected:
        for sentence in sentences_of(hit.text):
            if supports(sentence, hit.text) and sentence not in sentences:
                sentences.append(sentence)
                citations.append(_citation(hit))
                break
    draft = AssistantOutput(
        status="answered",
        answer=" ".join(sentences),
        citations=citations,
        uncertainties=uncertainties,
    )
    verified = verify_output(draft, hits)
    if verified.status != "answered":
        return verified
    if _ticket_requested(question):
        if not equipment_id:
            return verified.model_copy(
                update={
                    "status": "needs_clarification",
                    "clarification_question": "Pour quel équipement le ticket doit-il être préparé ?",
                }
            )
        action = ProposedAction(
            equipment_id=equipment_id,
            title=f"Contrôle documentaire {equipment_id}",
            description=(
                verified.answer
                + " Brouillon soumis à validation humaine. Ceci n'est pas un diagnostic."
            ),
        )
        return verified.model_copy(update={"status": "awaiting_approval", "proposed_action": action})
    return verified
