from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request
from pydantic import ValidationError

from models import SurveySubmission
from storage import DEFAULT_DATA_FILE, append_record


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.setdefault("SURVEY_DATA_FILE", str(DEFAULT_DATA_FILE))

    @app.after_request
    def apply_cors_headers(response):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
        response.headers.setdefault("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response

    @app.route("/ping", methods=["GET"])
    def ping() -> Any:
        payload: Dict[str, Any] = {
            "message": "API is alive",
            "status": "ok",
            "utc_time": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(payload), 200

    @app.route("/v1/survey", methods=["POST", "OPTIONS"])
    def submit_survey() -> Any:
        if request.method == "OPTIONS":
            return "", 204

        payload = request.get_json(silent=True)
        if payload is None:
            return (
                jsonify({"error": "invalid_json", "message": "Request body must be JSON"}),
                400,
            )

        try:
            submission = SurveySubmission(**payload)
        except ValidationError as exc:
            return (
                jsonify({"error": "validation_error", "details": exc.errors()}),
                422,
            )

        if not submission.user_agent:
            header_user_agent = request.headers.get("User-Agent")
            if header_user_agent:
                submission.user_agent = header_user_agent

        now = datetime.now(timezone.utc)
        record = submission.to_storage_record(now)

        data_file = Path(app.config["SURVEY_DATA_FILE"])
        append_record(record, data_file)

        return (
            jsonify({"status": "accepted", "submission_id": record["submission_id"]}),
            201,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
