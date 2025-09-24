from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_DATA_FILE = DATA_DIR / "survey.ndjson"


def append_record(record: Mapping[str, Any], file_path: Path | str = DEFAULT_DATA_FILE) -> None:
    """Append a single JSON record to the newline-delimited data file."""
    target_path = Path(file_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with target_path.open("a", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
        handle.write("\n")
