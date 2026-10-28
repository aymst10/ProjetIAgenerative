"""Construit l'index local et enregistre les métadonnées des éléments."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from maintidoc.ingest.pipeline import ingest


def main() -> None:
    index = ingest()
    documents = {element.document_id for element in index.elements}
    print(f"documents={len(documents)} elements={len(index.elements)}")


if __name__ == "__main__":
    main()
