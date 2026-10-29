"""Contrôle d'accès avant recherche et à l'ouverture."""

from maintidoc.corpus_data import user_by_id
from maintidoc.retrieval.search import read_document, read_figure, search_corpus


def test_visitor_is_denied():
    outcome = search_corpus("voyant orange", ["visiteur"], equipment_id="POMPE-A", user_id="bob")
    assert outcome.access_denied
    assert outcome.hits == []


def test_family_isolation_and_file_open():
    alice = user_by_id("alice")
    denied = search_corpus("huile", alice["groups"], equipment_id="COMP-A", user_id="alice")
    assert denied.access_denied
    blob = read_document("manuel_pompe_a", alice["groups"], "alice")
    assert blob.startswith(b"%PDF")
    try:
        read_document("manuel_comp_a", alice["groups"], "alice")
        raise AssertionError("fuite")
    except PermissionError:
        pass
    try:
        read_figure("manuel_comp_a", "figure_6_2", alice["groups"], "alice")
        raise AssertionError("fuite figure")
    except PermissionError:
        pass


def test_responsible_sees_both_families():
    pumps = search_corpus("voyant orange POMPE-A", ["responsables"], equipment_id="POMPE-A", top_k=5)
    compressors = search_corpus("huile ISO VG 46 COMP-A", ["responsables"], equipment_id="COMP-A", top_k=5)
    assert pumps.hits and pumps.hits[0].family == "pompes"
    assert compressors.hits and compressors.hits[0].document_id == "lubrification_comp_a"
