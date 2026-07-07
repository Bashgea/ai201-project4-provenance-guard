# Provenance Guard

A content-attribution service: creators submit text, two independent
detection signals estimate how likely it is to be AI-generated, the
scores combine into a single confidence value, and that value maps to
a transparency label shown to readers. Creators can appeal a
classification; a human reviewer makes the final call.

Full design rationale (signals, thresholds, edge cases, architecture
diagram) lives in `planning.md`. This README documents what was
actually built, why, and what I'd change.

---

## Architecture

```
Creator --POST /submit--> Rate Limiter --> Detection Pipeline
                                              |
                              +---------------+---------------+
                              |                               |
                     Signal 1: Groq LLM                Signal 2: Stylometric
                     (semantic score 0-1)               (structural score 0-1)
                              |                               |
                              +---------------+---------------+
                                              |
                                     Confidence Scorer
                                              |
                                     Label Generator
                                              |
                                       Audit Log (JSON)
                                              |
                                   Creator receives response

Creator --POST /appeal--> Appeal Handler --> looks up + updates Audit Log
```

Five modules, each with one job: `signals.py` (Signal 1), `stylometric.py`
(Signal 2), `scoring.py` (combine scores → attribution → label text),
`log.py` (JSON-file audit log storage), `app.py` (Flask routes wiring
it together).

---

## Detection Signals — reasoning

**Signal 1 (Groq LLM classifier)** asks an LLM to judge tone, phrasing,
and contextual patterns — the things a statistical count can't see. I
weighted it higher (0.6 vs 0.4) because semantic judgment is harder to
fake than sentence statistics: a script can't easily "edit" its way out
of sounding contextually generic the way it can pad in some irregular
punctuation. The tradeoff is that it's also the least transparent
signal — I can't fully audit *why* it gave a score, only what it
returned.

**Signal 2 (stylometric heuristics)** computes three cheap, fully
auditable statistics — sentence-length standard deviation, type-token
ratio, and expressive-punctuation density — with zero dependency on an
external API. It exists specifically as a check the LLM can't talk its
way around: even a well-prompted AI mimicking human irregularity still
has to actually vary its sentence lengths and vocabulary to fool this
signal, it can't just claim to.

Combining them the way I did (weighted average, not a vote or a max)
means the two signals can partially cancel each other out — which is
intentional. If they agree, the combined score moves confidently toward
0 or 1. If they disagree, the average lands in the middle, which is
exactly the "uncertain" band. Disagreement itself is information.

**If I were deploying this for real**, I'd change two things: (1) the
LLM signal isn't cached or batched, so cost scales linearly with
submissions — I'd add caching for repeat/near-duplicate text; (2) I'd
add a minimum-word-count guard before running Signal 2 at all (see
Known Limitations) instead of letting it produce a low-confidence
score dressed up as a real one.

---

## Confidence Scoring — reasoning and worked examples

```
confidence = (llm_score * 0.6) + (stylometric_score * 0.4)
```

Thresholds: `≤0.35` → human, `0.36–0.64` → uncertain, `≥0.65` → AI. The
uncertain band is deliberately wide. On a creative platform, wrongly
accusing a human of using AI is a worse failure than missing a real
AI submission — so when signals disagree, the system is built to say
"not sure" rather than force a verdict.

**Two real examples from testing**, same pipeline, actual logged
scores:

*High-confidence case* — input: *"Artificial intelligence represents a
transformative paradigm shift in modern society. It is important to
note that while the benefits of AI are numerous, it is equally
essential to consider the ethical implications..."*
→ `llm_score: 0.8`, `stylometric_score: 0.448`, **`confidence: 0.659`**
→ `attribution: ai`

*Low-confidence case* — input: *"ugh i rewrote this stupid essay four
times and i still hate the ending lol whatever its due in 10 min"*
→ `llm_score: 0.2`, `stylometric_score: 0.357`, **`confidence: 0.263`**
→ `attribution: human`

A ~0.40 spread between two inputs, landing correctly on opposite sides
of both thresholds, confirms the scoring function produces real
variation — not a constant hovering near 0.5.

---

## Transparency Labels — the exact text

**High-confidence AI** (`confidence ≥ 0.65`):
> Our system detected patterns strongly associated with AI-generated writing in this submission. This label does not prevent the work from being shared — it provides context for readers. If you wrote this yourself, you can file an appeal and a human reviewer will take a look.

**Uncertain** (`confidence 0.36–0.64`):
> Our system found mixed signals in this submission and could not make a confident determination. This content is marked as uncertain. If you believe this label is incorrect, you can file an appeal.

**High-confidence human** (`confidence ≤ 0.35`):
> Our system found no strong indicators of AI-generated writing in this submission. This work appears to be human-authored.

All three were verified reachable by live-testing three inputs
engineered to land in each band (see confidence scoring examples
above and `planning.md`'s Anticipated Edge Cases for the borderline
tests).

---

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
Lets a creator contest their classification. Only the original
submitter can appeal (`creator_id` must match the original
submission) — a mismatch returns `403`, an unknown `content_id`
returns `404`. No automated re-classification happens; a human
reviewer makes the final call by reading the appeal queue.

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
    "creator_id": "string",
    "timestamp": "string",
    "attribution": "string",
    "confidence": "float",
    "signals": {
      "llm_score": "float",
      "stylometric_score": "float"
    },
    "status": "classified | under_review",
    "appeal": null
  }
]
```

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

---

## Known Limitations

**Formal, academic human writing gets misread as AI.** This isn't
generic — it's a direct consequence of how Signal 1 works. The LLM
classifier associates clean structure, hedged claims ("it is important
to note"), and uniform tone with AI generation, but those are also the
exact markers of formal academic register. Tested live: a genuinely
human paragraph about monetary policy and asset-price inflation scored
`llm_score: 0.7–0.8` (AI-leaning) purely because of its register, not
its content. Signal 2 doesn't rescue this case either — formal writing
also tends to have low punctuation-density and moderate sentence
uniformity, the same statistical shape as AI text, so both signals
lean the same wrong direction together instead of disagreeing. A
graduate student or non-native English speaker writing in a
formal register is the most likely person to be falsely flagged by
this system, which is exactly why the appeal path exists.

The mirror-image failure also exists and is accepted by design: a
person who generates AI text and lightly edits it for irregularity
(varied sentence length, informal punctuation) can suppress both
signals into a "human" verdict — tested live at `confidence: 0.25–0.30`
for such a sample. Per planning.md's Edge Case 2, this is treated as
an acceptable false negative given the platform's asymmetric cost of
false accusations, not a bug to be silently patched over.

---

## Spec Reflection

**Where the spec helped:** the exact confidence thresholds
(`≤0.35 / 0.36–0.64 / ≥0.65`) and the exact transparency-label strings
in `planning.md` meant there was zero ambiguity to resolve during
implementation — `attribution_for_confidence()` and the label lookup
table are almost direct transcriptions of the spec, not judgment
calls. That's exactly what a spec should do: remove decisions that
don't need to be made twice.

**Where implementation diverged:** the spec says Signal 2's score is
"computed by averaging the three normalized sub-scores" but doesn't
specify *how* to normalize a raw metric (e.g. a sentence-length stdev
of 6.5 words) into a 0–1 sub-score — only that low values should lean
AI. My first implementation used a linear clamp that fully saturated
to `0.0` past 2x the spec's threshold. In testing, every real
multi-sentence paragraph I tried — AI or human — landed past that
saturation point, so the sub-score was constant across all inputs and
contributed nothing. I replaced it with a logistic curve, still
centered at the spec's threshold value but decaying smoothly instead
of flooring. The spec correctly defined *what* the metric should
measure and *which direction* it should point; the actual shape of the
scoring curve was left to implementation, and the first shape I picked
was wrong in a way only empirical testing against real text surfaced.

---

## AI Usage

This project was built with Claude Code as an implementation partner,
prompted against the sections of `planning.md` relevant to each
milestone rather than given the whole spec at once.

**Instance 1 — stylometric normalization bug.** I directed the AI to
implement Signal 2 per planning.md's three metrics. It produced a
version using a linear clamp to normalize each raw metric into a 0–1
score. When I asked it to test that function independently against
four deliberately different inputs (clearly AI, clearly human, two
borderline), the `sentence_variance` sub-score came back as exactly
`0.0` for all four — a real bug, not just a bad example. I had it
print the raw pre-normalization stdev values to diagnose, which showed
all four real paragraphs landing past the clamp's saturation point. I
directed it to replace the linear clamp with a logistic curve instead
of just "fixing the constant," and re-verified all four cases produced
distinct, non-saturated sub-scores before accepting the change.

**Instance 2 — following the project's own contract over generic
milestone wording.** At two points, the milestone instructions I gave
the AI used field names that didn't match this project's own
established API contract (`text` instead of `content` in one case,
`creator_reasoning` instead of `creator_id`+`reasoning` in another).
Rather than pasting those generic examples in literally, the AI
flagged the mismatch, kept the field names actually documented in this
README/planning.md, and asked me to confirm rather than silently
picking one. That's the behavior I wanted — a spec I wrote earlier
should win over a generic instruction template, and divergences from
my own contract should be surfaced, not silently resolved.

---

## Portfolio Walkthrough

*(Recorded separately — a short screen-capture walking through
`/submit` producing each of the three label bands, an `/appeal` call,
and the resulting `/log` entries.)*
