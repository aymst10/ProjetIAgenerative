"""Métadonnées documentaires. SQLite en local, PostgreSQL si DATABASE_URL l'indique."""

from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy import Boolean, Integer, String, Text, create_engine, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from maintidoc.config import Settings, get_settings
from maintidoc.ingest.elements import Element


class Base(DeclarativeBase):
    pass


class ElementRow(Base):
    __tablename__ = "elements"

    element_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(120), index=True)
    document_version: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    page: Mapped[int] = mapped_column(Integer)
    element_id: Mapped[str] = mapped_column(String(80))
    element_type: Mapped[str] = mapped_column(String(40))
    family: Mapped[str] = mapped_column(String(40))
    equipment_ids: Mapped[str] = mapped_column(Text)
    allowed_groups: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    injection: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_text: Mapped[str] = mapped_column(Text, default="")


def _sqlite_path(url: str, settings: Settings):
    from pathlib import Path

    raw = url.removeprefix("sqlite:///")
    target = Path(raw)
    if not target.is_absolute():
        target = settings.root / raw
    return target


def _engine(settings: Settings):
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if settings.database_url != "sqlite:///:memory:":
            _sqlite_path(settings.database_url, settings).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, connect_args=connect_args)


@lru_cache(maxsize=1)
def get_engine():
    engine = _engine(get_settings())
    Base.metadata.create_all(engine)
    return engine


def reset_metadata() -> None:
    get_engine.cache_clear()


def replace_elements(elements: list[Element], settings: Settings | None = None) -> None:
    engine = get_engine() if settings is None else _engine(settings)
    if settings is not None:
        Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(delete(ElementRow))
        for element in elements:
            session.add(
                ElementRow(
                    element_key=element.key,
                    document_id=element.document_id,
                    document_version=element.document_version,
                    title=element.title,
                    page=element.page,
                    element_id=element.element_id,
                    element_type=element.element_type,
                    family=element.family,
                    equipment_ids=json.dumps(element.equipment_ids, ensure_ascii=False),
                    allowed_groups=json.dumps(element.allowed_groups, ensure_ascii=False),
                    text=element.text,
                    image_path=element.image_path,
                    injection=element.injection,
                    ocr_text=element.ocr_text,
                )
            )
        session.commit()
