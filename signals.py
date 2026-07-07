import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a content attribution classifier. Given a \
piece of text, decide how likely it is to be AI-generated versus \
human-written.

Respond with ONLY a JSON object in this exact shape:
{"llm_score": <float 0.0-1.0>, "reason": "<one-sentence reason>"}

llm_score of 1.0 means high confidence AI-generated.
llm_score of 0.0 means high confidence human-written.
"""


def get_llm_score(content: str) -> dict:
    """Signal 1: semantic/stylistic classifier.

    Returns a score, not a binary flag - {"llm_score": float 0.0-1.0,
    "reason": str}, per the spec in planning.md.
    """
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    result = json.loads(response.choices[0].message.content)
    return {
        "llm_score": float(result["llm_score"]),
        "reason": result["reason"],
    }
