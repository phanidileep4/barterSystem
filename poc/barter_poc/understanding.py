"""Turn one listing sentence into matching concepts.

Runs once when a listing is saved, never per pair. Two implementations:

- DictionaryUnderstanding: the engine's inspectable word list. Offline, free.
- ClaudeUnderstanding: asks Claude for concept tags, reusing the community's
  existing vocabulary so differently-worded offers and needs converge.
  Only the listing sentence is sent — never names, zones, or history.

Owners can always see and correct the result; safety notes stay deterministic
in the engine regardless of which one ran.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

from barter.understand import understand as dictionary_understand

log = logging.getLogger(__name__)

# Deterministic screen applied in every mode. A hit holds the listing for a
# human steward instead of matching it.
HOLD_WORDS = {"cash", "loan", "password", "drugs", "weapon", "gun", "escort", "massage", "crypto"}


@dataclass
class Understood:
    concepts: List[str]
    source: str  # "dictionary" | "claude"
    hold_reason: Optional[str] = None


def screen(text: str) -> Optional[str]:
    words = set(text.lower().replace(",", " ").split())
    hits = sorted(words & HOLD_WORDS)
    return f"mentions {', '.join(hits)}; a steward will review it before matching" if hits else None


class DictionaryUnderstanding:
    name = "dictionary"

    def understand(self, kind: str, text: str, vocabulary: Iterable[str] = ()) -> Understood:
        return Understood(sorted(dictionary_understand(text).concepts), "dictionary", screen(text))


SYSTEM = """You help a neighbourhood exchange app understand listings. People list what they \
can offer and what they need, in their own words. Your tags are compared between offers and \
needs to suggest exchanges, so an offer and a need about the same thing must share tags even \
when worded differently.

For the listing, return 3 to 6 short lowercase tags describing WHAT is offered or needed: the \
most literal tag first, then broader ones (e.g. "web design", "website", "online presence"). \
Reuse tags from the existing vocabulary whenever one fits. Never tag who the person is, where \
they live, or when they are free.

Set needs_review to true only if the listing looks unsafe, illegal, sexual, deceptive, or \
like paid work disguised as an exchange, and say why in review_reason (otherwise "")."""

SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {"type": "array", "items": {"type": "string"}},
        "needs_review": {"type": "boolean"},
        "review_reason": {"type": "string"},
    },
    "required": ["concepts", "needs_review", "review_reason"],
    "additionalProperties": False,
}


class ClaudeUnderstanding:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model
        self.fallback = DictionaryUnderstanding()
        self.available = True

    @property
    def name(self) -> str:
        return "claude" if self.available else "dictionary"

    def understand(self, kind: str, text: str, vocabulary: Iterable[str] = ()) -> Understood:
        import anthropic

        if not self.available:
            return self.fallback.understand(kind, text)
        hold = screen(text)
        vocab = ", ".join(sorted(set(vocabulary))[:300]) or "(empty)"
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
                system=SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"Existing vocabulary: {vocab}\n\nListing ({kind}): {text}",
                }],
            )
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, TypeError):
            # TypeError: the SDK found no credentials at all when building the request.
            log.warning("Claude credentials missing or rejected; using dictionary from now on")
            self.available = False
            return self.fallback.understand(kind, text)
        except anthropic.APIConnectionError:
            log.warning("Claude unreachable; using dictionary")
            return self.fallback.understand(kind, text)
        except anthropic.APIStatusError as e:
            log.warning("Claude error %s (request %s); using dictionary", e.status_code, e.request_id)
            return self.fallback.understand(kind, text)

        if response.stop_reason == "refusal":
            return Understood(sorted(dictionary_understand(text).concepts), "dictionary",
                              hold or "could not be processed automatically; a steward will review it")
        body = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return self.fallback.understand(kind, text)

        concepts = sorted({c.strip().lower() for c in data["concepts"] if c.strip()})
        if data["needs_review"]:
            hold = hold or (data["review_reason"] or "flagged for review") + "; a steward will review it"
        return Understood(concepts, "claude", hold)


def from_environment():
    """Claude when the SDK is installed and credentials resolve; dictionary otherwise."""
    if os.environ.get("BARTER_UNDERSTANDING", "").lower() == "dictionary":
        return DictionaryUnderstanding()
    try:
        import anthropic
    except ImportError:
        return DictionaryUnderstanding()
    try:
        client = anthropic.Anthropic()
    except Exception as e:  # no credentials configured
        log.info("Claude not configured (%s); using dictionary", e)
        return DictionaryUnderstanding()
    return ClaudeUnderstanding(client, os.environ.get("BARTER_MODEL", "claude-opus-5-5"))
