import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from log import append_log_entry, get_log
from scoring import attribution_for_confidence, compute_confidence, short_label_for_confidence
from signals import get_llm_score
from stylometric import get_stylometric_score

app = Flask(__name__)


@app.route("/submit", methods=["POST"])
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
        "label": short_label_for_confidence(confidence),
        "signals": entry["signals"],
    }), 200


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", type=int)
    creator_id = request.args.get("creator_id")
    return jsonify(get_log(limit=limit, creator_id=creator_id))


if __name__ == "__main__":
    app.run(debug=True)
