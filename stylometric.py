import math
import re
import statistics

SENTENCE_VARIANCE_THRESHOLD = 3.0
TTR_THRESHOLD = 0.6
PUNCTUATION_DENSITY_THRESHOLD = 0.2

EXPRESSIVE_PUNCTUATION = re.compile(r"!|\?|—|\.\.\.")


def _split_sentences(content: str) -> list:
    return [s.strip() for s in re.split(r"[.!?]+", content) if s.strip()]


def _low_value_suggests_ai(value: float, threshold: float) -> float:
    """Maps a raw metric to a 0.0-1.0 sub-score where values below the
    spec's threshold lean AI. value == threshold lands exactly at 0.5.

    Uses a logistic curve rather than a linear clamp: a hard cutoff at
    2x the threshold flattens to 0.0 for most real multi-sentence text
    (whose raw sentence-length stdev commonly lands at 2-3x threshold),
    destroying this sub-signal's discriminative power. The logistic
    keeps differentiating smoothly as value grows instead of flooring.
    """
    return 1 / (1 + math.exp((value - threshold) / threshold))


def get_stylometric_score(content: str) -> dict:
    """Signal 2: pure-Python structural/statistical heuristics.

    Returns a score, not a binary flag - {"stylometric_score": float
    0.0-1.0, "breakdown": {...}}, per the spec in planning.md.
    """
    sentences = _split_sentences(content)
    sentence_lengths = [len(s.split()) for s in sentences]
    sentence_std = statistics.stdev(sentence_lengths) if len(sentence_lengths) >= 2 else 0.0

    words = re.findall(r"\b\w+\b", content.lower())
    ttr = len(set(words)) / len(words) if words else 0.0

    punctuation_count = len(EXPRESSIVE_PUNCTUATION.findall(content))
    punctuation_density = punctuation_count / len(sentences) if sentences else 0.0

    sentence_variance_score = _low_value_suggests_ai(sentence_std, SENTENCE_VARIANCE_THRESHOLD)
    type_token_ratio_score = _low_value_suggests_ai(ttr, TTR_THRESHOLD)
    punctuation_density_score = _low_value_suggests_ai(punctuation_density, PUNCTUATION_DENSITY_THRESHOLD)

    stylometric_score = (
        sentence_variance_score + type_token_ratio_score + punctuation_density_score
    ) / 3

    return {
        "stylometric_score": stylometric_score,
        "breakdown": {
            "sentence_variance": sentence_variance_score,
            "type_token_ratio": type_token_ratio_score,
            "punctuation_density": punctuation_density_score,
        },
    }
