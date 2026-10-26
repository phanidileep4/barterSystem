"""Step 1 — Understand: turn plain-language listings into concepts.

This is a small, inspectable dictionary standing in for an AI step. A future
`ClaudeUnderstanding` can implement the same `concepts()` / `compare()` shape;
this version then stays as the offline fallback and as a test oracle.
"""

import re
from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple

# word -> concept. Words not listed here become their own concept.
CONCEPTS: Dict[str, str] = {
    # teaching
    "tutoring": "teaching", "tutor": "teaching", "lesson": "teaching", "lessons": "teaching",
    "teach": "teaching", "teaching": "teaching", "coaching": "teaching", "coach": "teaching",
    "practice": "teaching", "class": "teaching", "classes": "teaching",
    "maths": "math", "mathematics": "math",
    # careers
    "resume": "resume", "cv": "resume", "review": "feedback", "feedback": "feedback", "critique": "feedback",
    # repair and home
    "fix": "repair", "repair": "repair", "repairs": "repair", "tune": "repair", "mend": "repair",
    "plumbing": "plumbing", "plumber": "plumbing", "faucet": "plumbing", "faucets": "plumbing",
    "tap": "plumbing", "drain": "plumbing", "drains": "plumbing", "leak": "plumbing", "leaks": "plumbing",
    "leaking": "plumbing", "dripping": "plumbing", "shower": "plumbing",
    "kitchen": "home", "flat": "home", "apartment": "home", "house": "home", "home": "home",
    # photography
    "photo": "photography", "photos": "photography", "photography": "photography",
    "headshot": "photography", "portrait": "photography",
    # food
    "cooked": "cooking", "cook": "cooking", "cooking": "cooking", "meals": "cooking",
    "meal": "cooking", "dinners": "cooking", "dinner": "cooking",
    # moving
    "moving": "moving", "move": "moving", "boxes": "moving", "lifting": "moving",
    # bikes, music, pets
    "bike": "bicycle", "bicycle": "bicycle", "cycle": "bicycle",
    "piano": "music", "guitar": "music", "music": "music",
    "dog": "pets", "dogs": "pets", "pet": "pets", "cat": "pets", "walking": "pets", "sitting": "pets",
    # small business
    "website": "website", "websites": "website", "business": "business", "businesses": "business",
    # paperwork
    "tax": "tax", "taxes": "tax", "preparing": "preparation", "prepare": "preparation",
    # help
    "help": "help", "someone": "help",
}

# Broad concepts count for less: "help" alone should never make a match.
GENERIC_WEIGHT = 0.5
GENERIC = {"teaching", "repair", "help", "home"}

# Words that describe who is involved, not what is exchanged. They never
# drive matching, but some of them trigger safety guidance.
MINOR_WORDS = {"son", "daughter", "child", "children", "kid", "kids", "teen", "teenage", "teenager"}

STOPWORDS = {
    "a", "an", "and", "the", "for", "my", "to", "of", "in", "on", "with", "at", "into", "during",
    "before", "after", "up", "ups", "few", "times", "week", "month", "new", "basic", "small",
    "beginner", "high", "school", "busy", "exam", "upcoming", "trip", "road", "heavy", "profile",
    "linkedin", "look", "conversation", "pitch", "some",
}


@dataclass(frozen=True)
class Understanding:
    concepts: FrozenSet[str]
    involves_minor: bool


def _words(text: str):
    return re.findall(r"[a-z]+", text.lower())


def understand(text: str) -> Understanding:
    words = _words(text)
    concepts = frozenset(
        CONCEPTS.get(w, w) for w in words
        if len(w) > 1 and w not in STOPWORDS and w not in MINOR_WORDS
    )
    return Understanding(concepts=concepts, involves_minor=any(w in MINOR_WORDS for w in words))


def _weight(concept: str) -> float:
    return GENERIC_WEIGHT if concept in GENERIC else 1.0


def compare(offer_text: str, need_text: str) -> Tuple[float, FrozenSet[str]]:
    """How much of the need does the offer cover? Returns (0..1, shared concepts)."""
    return compare_concepts(understand(offer_text).concepts, understand(need_text).concepts)


def compare_concepts(offer: FrozenSet[str], need: FrozenSet[str]) -> Tuple[float, FrozenSet[str]]:
    if not need:
        return 0.0, frozenset()
    shared = offer & need
    # A match built only on generic concepts ("help", "repair") is not a match.
    if all(c in GENERIC for c in shared):
        return 0.0, frozenset(shared)
    score = sum(_weight(c) for c in shared) / sum(_weight(c) for c in need)
    return round(score, 2), frozenset(shared)
