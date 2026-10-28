"""Découpe les PDF du corpus en éléments avec leurs métadonnées d'accès."""

from __future__ import annotations

import re

from maintidoc.corpus_data import CORPUS, documents
from maintidoc.ingest.elements import Element
from maintidoc.logging_utils import log_event

try:
    import pymupdf as fitz
except ImportError:
    import fitz

ELEMENT_RE = re.compile(
    r"@@ELEM id=(\S+) type=(\w+)@@\s*(.*?)\s*@@END@@",
    re.DOTALL,
)


def _ocr_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ocr(path) -> str:
    import pytesseract
    from PIL import Image

    return " ".join(pytesseract.image_to_string(Image.open(path), lang="fra").split())


def _extract_pdf(path) -> dict[tuple[int, str], str]:
    found: dict[tuple[int, str], str] = {}
    pdf = fitz.open(path)
    try:
        for index, page in enumerate(pdf, start=1):
            for match in ELEMENT_RE.finditer(page.get_text()):
                found[(index, match.group(1))] = " ".join(match.group(3).split())
    finally:
        pdf.close()
    return found


def load_elements() -> list[Element]:
    ocr_ready = _ocr_available()
    ocr_logged: set[str] = set()
    elements: list[Element] = []
    for document in documents():
        pdf_path = CORPUS / document["file"]
        extracted = _extract_pdf(pdf_path)
        for page in document["pages"]:
            for raw in page["elements"]:
                key = (page["page"], raw["element_id"])
                text = extracted.get(key, "")
                if not text:
                    text = " ".join(raw["text"].split())
                    log_event(
                        "parse_fallback",
                        document_id=document["document_id"],
                        page=page["page"],
                        element_id=raw["element_id"],
                    )
                image_rel = raw.get("image")
                ocr_text = ""
                if raw["type"] == "figure":
                    if not ocr_ready:
                        if document["document_id"] not in ocr_logged:
                            log_event(
                                "ocr_skipped",
                                document_id=document["document_id"],
                                page=page["page"],
                                reason="tesseract_absent",
                            )
                            ocr_logged.add(document["document_id"])
                    elif image_rel:
                        try:
                            ocr_text = _ocr(CORPUS / image_rel)
                        except Exception:
                            log_event(
                                "ocr_skipped",
                                document_id=document["document_id"],
                                page=page["page"],
                                reason="ocr_failed",
                            )
                elements.append(
                    Element(
                        document_id=document["document_id"],
                        document_version=document["version"],
                        title=document["title"],
                        page=page["page"],
                        element_id=raw["element_id"],
                        element_type=raw["type"],
                        family=document["family"],
                        equipment_ids=list(document["equipment_ids"]),
                        allowed_groups=list(document["allowed_groups"]),
                        text=text,
                        image_path=image_rel,
                        injection=bool(document.get("injection")),
                        ocr_text=ocr_text,
                    )
                )
    return elements
