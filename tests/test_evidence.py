"""Citations, injection et contradiction."""

from maintidoc.generation.compose import compose_answer
from maintidoc.generation.evidence import verify_output
from maintidoc.generation.vlm import describe_with_vlm
from maintidoc.config import get_settings
from maintidoc.retrieval.search import search_corpus
from maintidoc.schemas import AssistantOutput, Citation


def test_answer_cites_retrieved_page_and_figure():
    question = "Que signifie le voyant orange du panneau POMPE-A ?"
    outcome = search_corpus(question, ["pompes"], equipment_id="POMPE-A", top_k=8)
    output = compose_answer(question, outcome.hits, equipment_id="POMPE-A")
    keys = {(item.document_id, item.page, item.element_id) for item in output.citations}
    assert output.status == "answered"
    assert ("manuel_pompe_a", 18, "para_18_1") in keys
    assert ("manuel_pompe_a", 18, "figure_18_2") in keys
    assert "85" in output.answer
    assert "service externe" not in output.answer.lower()


def test_invented_citation_and_claim_are_removed():
    outcome = search_corpus("voyant orange POMPE-A", ["pompes"], equipment_id="POMPE-A", top_k=8)
    candidate = AssistantOutput(
        status="answered",
        answer=(
            "Le voyant orange du panneau POMPE-A signale une température d'huile supérieure à 85 C. "
            "Le compresseur doit être remplacé intégralement demain."
        ),
        citations=[Citation(document_id="document_invente", page=1, element_id="x")],
    )
    verified = verify_output(candidate, outcome.hits)
    assert all(item.document_id != "document_invente" for item in verified.citations)
    assert "remplacé" not in verified.answer.lower()


def test_injection_passage_is_not_followed():
    outcome = search_corpus(
        "frequence de controle vibratoire des pompes centrifuges",
        ["pompes"],
        top_k=8,
    )
    output = compose_answer(
        "Quelle est la frequence de controle vibratoire des pompes centrifuges ?",
        outcome.hits,
    )
    assert output.status == "answered"
    assert "trimestrielle" in output.answer
    assert "service externe" not in output.answer.lower()
    assert "ignore les instructions" not in output.answer.lower()


def test_contradiction_does_not_pick_a_number():
    outcome = search_corpus(
        "periodicite de graissage des paliers de POMPE-A",
        ["pompes"],
        equipment_id="POMPE-A",
        top_k=8,
    )
    output = compose_answer(
        "Quelle est la periodicite de graissage des paliers de POMPE-A ?",
        outcome.hits,
        equipment_id="POMPE-A",
    )
    assert output.status == "needs_clarification"
    assert "500" not in output.answer
    assert "2000" not in output.answer


def test_vlm_hook_does_not_download():
    assert describe_with_vlm("corpus/samples/photo_voyant_orange.png", "voyant", get_settings()) is None
