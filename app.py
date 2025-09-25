from datetime import datetime, timezone
import logging
import time
import uuid
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission
from storage import append_json_line, iter_json_lines, RESULTS_PATH

app = Flask(__name__)
# Allow cross-origin requests so the static HTML can POST from localhost or file://
CORS(app, resources={r"/v1/*": {"origins": "*"}})
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("survey_api")


@app.before_request
def _start_timer():
    request._start_time = time.time()
    request._request_id = str(uuid.uuid4())


@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify(
        {
            "status": "ok",
            "message": "API is alive",
            "utc_time": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.route("/", methods=["GET"])
def index():
    # Serve the frontend index.html from ./frontend
    return send_from_directory("frontend", "index.html")


@app.route("/styles.css", methods=["GET"])
def styles():
    return send_from_directory("frontend", "styles.css")


@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return (
            jsonify({"error": "invalid_json", "message": "Request body must be JSON"}),
            400,
        )

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "details": ve.errors()}), 422

    # Enrich with user_agent and ip
    if not getattr(submission, "user_agent", None):
        ua = request.headers.get("User-Agent")
        if ua:
            submission.user_agent = ua

    now = datetime.now(timezone.utc)
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.access_route and request.access_route[0])
        or request.remote_addr
        or ""
    )
    record = submission.to_storage_record(now, ip=client_ip)

    # Dedupe by submission_id + exact same payload fields
    is_dup = False
    for existing in iter_json_lines(RESULTS_PATH):
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
            is_dup = True
            break

    if not is_dup:
        append_json_line(record)

    return jsonify({"status": "ok", "submission_id": record["submission_id"]}), 201


@app.after_request
def _log(response):
    latency_ms = int(
        (time.time() - getattr(request, "_start_time", time.time())) * 1000
    )
    logger.info(
        {
            "request_id": getattr(request, "_request_id", "-"),
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "latency_ms": latency_ms,
        }
    )
    return response


if __name__ == "__main__":
    app.run(debug=True)
