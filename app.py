from __future__ import annotations

from datetime import datetime, timezone
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request, send_from_directory
from pydantic import ValidationError

from models import SurveySubmission
from storage import DEFAULT_DATA_FILE, append_record, iter_records


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.setdefault("SURVEY_DATA_FILE", str(DEFAULT_DATA_FILE))

    # Basic structured logging setup
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger("survey_api")

    @app.before_request
    def start_timer_and_request_id():
        request._start_time = time.time()
        request._request_id = str(uuid.uuid4())

    @app.after_request
    def apply_cors_headers(response):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
        response.headers.setdefault("Access-Control-Allow-Methods", "POST, OPTIONS")
        # Log after request with latency and status, without PII
        if hasattr(request, "_start_time"):
            latency_ms = int((time.time() - getattr(request, "_start_time", time.time())) * 1000)
        else:
            latency_ms = -1
        request_id = getattr(request, "_request_id", "-")
        logger.info(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": latency_ms,
            }
        )
        return response

    @app.route("/ping", methods=["GET"])
    def ping() -> Any:
        payload: Dict[str, Any] = {
            "message": "API is alive",
            "status": "ok",
            "utc_time": datetime.now(timezone.utc).isoformat(),
        }
        return jsonify(payload), 200

    # Serve minimal frontend from the same Flask server
    @app.route("/", methods=["GET"])
    def index() -> Any:
        frontend_dir = Path(__file__).parent / "frontend"
        return send_from_directory(str(frontend_dir), "index.html")

    @app.route("/styles.css", methods=["GET"])
    def styles() -> Any:
        frontend_dir = Path(__file__).parent / "frontend"
        return send_from_directory(str(frontend_dir), "styles.css")

    @app.route("/v1/survey", methods=["POST", "OPTIONS"])
    def submit_survey() -> Any:
        if request.method == "OPTIONS":
            return "", 204

        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"error": "invalid_json", "message": "Request body must be JSON"}), 400

        try:
            submission = SurveySubmission(**payload)
        except ValidationError as exc:
            return jsonify({"error": "validation_error", "details": exc.errors()}), 422

        if not submission.user_agent:
            header_user_agent = request.headers.get("User-Agent")
            if header_user_agent:
                submission.user_agent = header_user_agent

        now = datetime.now(timezone.utc)
        # Enrich with IP and header-derived UA if missing already handled above
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.access_route and request.access_route[0])
            or request.remote_addr
        )
        record = submission.to_storage_record(now, ip=client_ip)

        data_file = Path(app.config["SURVEY_DATA_FILE"])
        # Idempotency / dedupe: drop exact duplicates for same submission_id
        is_duplicate = False
        for existing in iter_records(data_file):
            if (
                existing.get("submission_id") == record.get("submission_id")
                and existing.get("email") == record.get("email")
                and existing.get("age") == record.get("age")
                and existing.get("name") == record.get("name")
                and existing.get("consent") == record.get("consent")
                and existing.get("rating") == record.get("rating")
                and existing.get("comments") == record.get("comments")
                and existing.get("source") == record.get("source")
            ):
                is_duplicate = True
                break

        if not is_duplicate:
            append_record(record, data_file)

        return jsonify({"status": "ok", "submission_id": record["submission_id"]}), 201

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
