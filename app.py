import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request

from log import append_log_entry, get_log
from signals import get_llm_score

app = Flask(__name__)


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True) or {}
    content = data.get("content")
    creator_id = data.get("creator_id")

    if not content or not creator_id:
        return jsonify({"error": "content and creator_id are required"}), 400

    llm_result = get_llm_score(content)

    # Stylometric signal + confidence scoring land in M4.
    entry = {
        "content_id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "attribution": "uncertain",
        "confidence": llm_result["llm_score"],
        "signals": {
            "llm_score": llm_result["llm_score"],
            "stylometric_score": None,
        },
        "status": "classified",
        "appeal": None,
    }
    append_log_entry(entry)

    return jsonify({
        "content_id": entry["content_id"],
        "attribution": entry["attribution"],
        "confidence": entry["confidence"],
        "label": None,
        "signals": entry["signals"],
    }), 200


@app.route("/log", methods=["GET"])
def log():
    limit = request.args.get("limit", type=int)
    creator_id = request.args.get("creator_id")
    return jsonify(get_log(limit=limit, creator_id=creator_id))


if __name__ == "__main__":
    app.run(debug=True)
