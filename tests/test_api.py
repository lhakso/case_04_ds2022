from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator

import pytest

from app import create_app
from models import compute_submission_id, hash_text


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app()
    app.config.update(
        TESTING=True,
        SURVEY_DATA_FILE=str(tmp_path / "survey.ndjson"),
    )

    with app.test_client() as test_client:
        yield test_client


def load_records(file_path: Path) -> Iterator[Dict]:
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def test_ping_returns_status(client):
    response = client.get("/ping")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["message"] == "API is alive"
    assert payload["status"] == "ok"
    datetime.fromisoformat(payload["utc_time"])  # raises if malformed


def test_submit_valid_payload_persists_hashed_data(client):
    data_file = Path(client.application.config["SURVEY_DATA_FILE"])

    payload = {
        "name": "Ava",
        "email": "ava@example.com",
        "age": 22,
        "consent": True,
        "rating": 5,
        "comments": "Great!",
        "user_agent": "frontend-test",
        "source": "web",
    }

    response = client.post("/v1/survey", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["status"] == "ok"
    assert len(body["submission_id"]) == 64
    assert response.headers["Access-Control-Allow-Origin"] == "*"

    records = list(load_records(data_file))
    assert len(records) == 1
    record = records[0]

    stored_time = datetime.fromisoformat(record["received_at"])
    expected_submission_id = compute_submission_id(payload["email"].lower(), stored_time)

    assert record["submission_id"] == expected_submission_id
    assert record["name"] == payload["name"]
    assert record["consent"] is True
    assert record["rating"] == payload["rating"]
    assert record["comments"] == payload["comments"]
    assert record["source"] == payload["source"]
    assert record["user_agent"] == payload["user_agent"]
    assert record["email"] == hash_text(payload["email"].lower())
    assert record["age"] == hash_text(str(payload["age"]))


def test_submit_uses_supplied_submission_id(client):
    data_file = Path(client.application.config["SURVEY_DATA_FILE"])

    payload = {
        "name": "Ravi",
        "email": "ravi@example.com",
        "age": 30,
        "consent": True,
        "rating": 4,
        "comments": "",
        "submission_id": "custom-id-123",
        "source": "mobile",
    }

    response = client.post("/v1/survey", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body["submission_id"] == "custom-id-123"

    record = next(load_records(data_file))
    assert record["submission_id"] == "custom-id-123"
    assert record["email"] == hash_text(payload["email"].lower())
    assert record["age"] == hash_text(str(payload["age"]))
    assert record["source"] == payload["source"]


def test_submit_rejects_invalid_payload(client):
    response = client.post(
        "/v1/survey",
        json={
            "name": "Ava",
            "age": 22,
            "consent": True,
            "rating": 5,
        },
    )
    assert response.status_code == 422
    body = response.get_json()
    assert body["error"] == "validation_error"
    assert any(item["loc"][-1] == "email" for item in body["details"])


def test_consent_must_be_true(client):
    response = client.post(
        "/v1/survey",
        json={
            "name": "Ava",
            "email": "ava@example.com",
            "age": 22,
            "consent": False,
            "rating": 5,
        },
    )
    assert response.status_code == 422
    details = response.get_json()["details"]
    assert any(item["loc"][-1] == "consent" for item in details)


def test_dedupe_by_submission_id(client):
    data_file = Path(client.application.config["SURVEY_DATA_FILE"])
    payload = {
        "name": "Ava",
        "email": "ava@example.com",
        "age": 22,
        "consent": True,
        "rating": 5,
        "comments": "Great!",
        "submission_id": "same-id",
        "source": "web",
    }
    r1 = client.post("/v1/survey", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/v1/survey", json=payload)
    assert r2.status_code == 201

    records = list(load_records(data_file))
    assert len(records) == 1


def test_submit_with_non_json_body_returns_error(client):
    response = client.post("/v1/survey", data="name=Ava")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "invalid_json"
    assert response.headers["Access-Control-Allow-Origin"] == "*"


def test_options_preflight_is_allowed(client):
    response = client.options("/v1/survey")
    assert response.status_code == 204
    assert response.data == b""
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
