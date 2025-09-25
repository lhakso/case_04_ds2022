import json
from pathlib import Path
from datetime import datetime
from typing import Mapping, Any, Iterator, Dict

RESULTS_PATH = Path("data/survey.ndjson")


def append_json_line(record: Mapping[str, Any]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                record,
                ensure_ascii=False,
                default=lambda o: o.isoformat() if isinstance(o, datetime) else o,
            )
            + "\n"
        )


def iter_json_lines(path: Path = RESULTS_PATH) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return iter(())

    def _gen() -> Iterator[Dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    return _gen()
