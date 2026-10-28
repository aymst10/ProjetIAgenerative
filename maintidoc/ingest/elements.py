"""Élément de corpus indexable."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Element:
    document_id: str
    document_version: str
    title: str
    page: int
    element_id: str
    element_type: str
    family: str
    equipment_ids: list[str]
    allowed_groups: list[str]
    text: str
    image_path: str | None
    injection: bool
    ocr_text: str = ""

    @property
    def key(self) -> str:
        return f"{self.document_id}:{self.page}:{self.element_id}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "Element":
        return cls(
            document_id=payload["document_id"],
            document_version=payload["document_version"],
            title=payload["title"],
            page=int(payload["page"]),
            element_id=payload["element_id"],
            element_type=payload["element_type"],
            family=payload["family"],
            equipment_ids=list(payload["equipment_ids"]),
            allowed_groups=list(payload["allowed_groups"]),
            text=payload["text"],
            image_path=payload.get("image_path"),
            injection=bool(payload.get("injection", False)),
            ocr_text=payload.get("ocr_text", ""),
        )
