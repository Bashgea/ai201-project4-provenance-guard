LLM_WEIGHT = 0.6
STYLOMETRIC_WEIGHT = 0.4

HUMAN_MAX = 0.35
AI_MIN = 0.65

# Exact strings from planning.md's Transparency Label Design section.
LABEL_TEXT = {
    "ai": (
        "Our system detected patterns strongly associated with "
        "AI-generated writing in this submission. This label does not "
        "prevent the work from being shared — it provides context for "
        "readers. If you wrote this yourself, you can file an appeal "
        "and a human reviewer will take a look."
    ),
    "uncertain": (
        "Our system found mixed signals in this submission and could "
        "not make a confident determination. This content is marked "
        "as uncertain. If you believe this label is incorrect, you "
        "can file an appeal."
    ),
    "human": (
        "Our system found no strong indicators of AI-generated writing "
        "in this submission. This work appears to be human-authored."
    ),
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


def label_for_confidence(confidence: float) -> str:
    return LABEL_TEXT[attribution_for_confidence(confidence)]
