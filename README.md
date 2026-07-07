## API Surface

### POST /submit
Accepts a piece of text content for attribution analysis.

**Request body:**
```json
{
  "content": "string",
  "creator_id": "string"
}
```

**Response:**
```json
{
  "content_id": "string",
  "attribution": "ai | human | uncertain",
  "confidence": "0.0 – 1.0",
  "label": "string (the transparency label shown to the user)",
  "signals": {
    "llm_score": "float",
    "stylometric_score": "float"
  }
}
```

---

### POST /appeal
Lets a creator contest their classification.

**Request body:**
```json
{
  "content_id": "string",
  "creator_id": "string",
  "reasoning": "string"
}
```

**Response:**
```json
{
  "appeal_id": "string",
  "status": "under_review",
  "message": "string (confirmation for the creator)"
}
```

---

### GET /log
Returns the audit log of all attribution decisions and appeals.

**Query params (optional):** `limit`, `creator_id`

**Response:**
```json
[
  {
    "content_id": "string",
    "timestamp": "string",
    "attribution": "string",
    "confidence": "float",
    "signals": {
      "llm_score": "float",
      "stylometric_score": "float"
    },
    "appeal": null
  }
]
```

---

## Why Confidence Scoring Is Designed This Way

A false positive — labeling a human writer's work as AI-generated
— is worse than a false negative on a creative platform. Wrongly
accusing a human creator damages trust visibly and publicly.
Missing an AI submission is a minor failure.

Because of this asymmetry, the system is designed to lean toward
uncertainty rather than confidence when signals conflict. A
minimalist poet who writes in short, controlled sentences may
score high on the stylometric signal but low on the LLM signal.
Rather than averaging to a false "high confidence AI" verdict,
conflicting signals push the score toward the uncertain range,
which produces a more cautious label and makes the appeal path
clearly visible to the creator.

---

## Rate Limiting

`POST /submit` is limited to **10 requests per minute and 100 per
day**, keyed by client IP (Flask-Limiter's default).

**Why these numbers:** a real writer submitting and revising their
own drafts in one sitting might hit the endpoint a handful of times
a minute at most — 10/minute comfortably covers that, including a
few rapid retries, while still blocking a script that tries to flood
the pipeline. 100/day covers a genuinely heavy day of revisions
across multiple pieces without letting an automated client hammer
the endpoint all day — each request costs a real Groq API call, so
the daily cap also bounds cost exposure.

**Evidence** — 12 rapid `POST /submit` calls from the same client,
back to back:
```
200
200
200
200
200
200
200
429
429
429
429
429
```
Only 7 show `200` here instead of 10 because 3 earlier requests in
the same test session had already counted against this IP's
1-minute window (3 + 7 = 10, then the limit engages) — confirming
the counter is working per-IP as configured, not per-request-batch.