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