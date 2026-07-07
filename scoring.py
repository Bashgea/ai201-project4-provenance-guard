LLM_WEIGHT = 0.6
STYLOMETRIC_WEIGHT = 0.4

HUMAN_MAX = 0.35
AI_MIN = 0.65

SHORT_LABELS = {
    "human": "Likely human-written",
    "uncertain": "Uncertain",
    "ai": "Likely AI-generated",
}


def compute_confidence(llm_score: float, stylometric_score: float) -> float:
    """Weighted average per planning.md: llm_score is weighted higher
    because it captures semantic context, which is harder to fake than
    the stylometric signal.
    """
    return (llm_score * LLM_WEIGHT) + (stylometric_score * STYLOMETRIC_WEIGHT)


def attribution_for_confidence(confidence: float) -> str:
    if confidence <= HUMAN_MAX:
        return "human"
    if confidence >= AI_MIN:
        return "ai"
    return "uncertain"


def short_label_for_confidence(confidence: float) -> str:
    """Short interim label. The full paragraph-form transparency text
    from planning.md's Transparency Label Design lands in M5.
    """
    return SHORT_LABELS[attribution_for_confidence(confidence)]
