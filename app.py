import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from log import add_appeal, append_log_entry, find_entry_by_content_id, get_log
from scoring import attribution_for_confidence, compute_confidence, label_for_confidence
from signals import get_llm_score
from stylometric import get_stylometric_score

app = Flask(__name__)

# 10/minute covers a writer submitting and re-submitting drafts in one
# sitting; 100/day covers a heavy day of revisions across many pieces
# without letting a script flood the pipeline (each call costs a real
# Groq API request).
limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    creator_id = data.get("creator_id")

    if not content or not creator_id:
        return jsonify({"error": "content and creator_id are required"}), 400

    llm_result = get_llm_score(content)
    stylometric_result = get_stylometric_score(content)

    confidence = compute_confidence(llm_result["llm_score"], stylometric_result["stylometric_score"])

    entry = {
        "content_id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": attribution_for_confidence(confidence),
        "confidence": confidence,
        "signals": {
            "llm_score": llm_result["llm_score"],
            "stylometric_score": stylometric_result["stylometric_score"],
        },
        "status": "classified",
        "appeal": None,
    }
    append_log_entry(entry)

    return jsonify({
        "content_id": entry["content_id"],
        "attribution": entry["attribution"],
        "confidence": entry["confidence"],
        "label": label_for_confidence(confidence),
        "signals": entry["signals"],
    }), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True) or {}
    content_id = data.get("content_id")
    creator_id = data.get("creator_id")
    reasoning = data.get("reasoning")

    if not content_id or not creator_id or not reasoning:
        return jsonify({"error": "content_id, creator_id, and reasoning are required"}), 400

    entry = find_entry_by_content_id(content_id)
    if entry is None:
        return jsonify({"error": "content_id not found"}), 404

    if entry["creator_id"] != creator_id:
        return jsonify({"error": "creator_id does not match the original submission"}), 403

    appeal_record = {
        "appeal_id": str(uuid.uuid4()),
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "under_review",
    }
    add_appeal(content_id, appeal_record)

    return jsonify({
        "appeal_id": appeal_record["appeal_id"],
        "status": "under_review",
        "message": "Your appeal has been received and is under review.",
    }), 200


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", type=int)
    creator_id = request.args.get("creator_id")
    return jsonify(get_log(limit=limit, creator_id=creator_id))


if __name__ == "__main__":
    app.run(debug=True)
