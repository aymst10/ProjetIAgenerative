"""Démarre l'interface Streamlit."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit.web import cli


def main() -> None:
    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "ui" / "streamlit_app.py"),
        "--server.port",
        "8501",
        "--server.address",
        "0.0.0.0",
        "--browser.gatherUsageStats",
        "false",
    ]
    cli.main()


if __name__ == "__main__":
    main()
