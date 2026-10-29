"""Démarre l'API MaintiDoc."""

import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    uvicorn.run("maintidoc.api.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
