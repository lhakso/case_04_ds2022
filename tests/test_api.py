from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator

import pytest

from app import app


@pytest.fixture()
def client(tmp_path: Path):
    app.testing = True
    app.config.update(SURVEY_DATA_FILE=str(tmp_path / "survey.ndjson"))
    with app.test_client() as c:
        yield c


def load_records(file_path: Path) -> Iterator[Dict]:
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def test_requires_json(client):
    r = client.post("/v1/survey", data="hi", headers={"Content-Type": "text/plain"})
    assert r.status_code == 400


def test_validation_error(client):
    bad = {"name": "", "email": "bad", "age": 9, "consent": False, "rating": 9}
    r = client.post("/v1/survey", json=bad)
    assert r.status_code == 422
    assert r.get_json()["error"] == "validation_error"


def test_happy_path(client):
    good = {
        "name": "Ava",
        "email": "ava@example.com",
        "age": 22,
        "consent": True,
        "rating": 4,
        "source": "web",
    }
    r = client.post("/v1/survey", json=good)
    assert r.status_code == 201
    body = r.get_json()
    assert body["status"] == "ok"
    assert len(body["submission_id"]) == 64
