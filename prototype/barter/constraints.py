"""Step 2 — Constrain: deterministic rules. No AI step may override these."""

from typing import List

from .models import Community, Listing, Participant


def is_blocked(a: Participant, b: Participant) -> bool:
    """Blocked pairs are invisible to each other: never matched, never a near miss,
    never mentioned in any explanation, so a block cannot be inferred."""
    return b.id in a.blocks or a.id in b.blocks


def check(community: Community, giver: Participant, offer: Listing,
          receiver: Participant, need: Listing) -> List[str]:
    """Return the reasons this offer cannot serve this need. Empty means allowed.
    Callers must drop blocked pairs before calling this."""
    reasons = []
    remote_ok = offer.mode in ("remote", "either") and need.mode in ("remote", "either")
    in_person_ok = offer.mode in ("in_person", "either") and need.mode in ("in_person", "either")

    if not remote_ok and not in_person_ok:
        reasons.append(f"one side is {offer.mode.replace('_', ' ')} only, the other {need.mode.replace('_', ' ')} only")
    elif not remote_ok:
        distance = community.zone_distance(giver.zone, receiver.zone)
        reach = max(giver.max_travel, receiver.max_travel)
        if distance is None or distance > reach:
            hops = "unconnected" if distance is None else f"{distance} zones apart"
            reasons.append(
                f"must meet in person but {giver.name} ({giver.zone}) and "
                f"{receiver.name} ({receiver.zone}) are {hops}; the furthest either travels is {reach}"
            )

    if not giver.availability & receiver.availability:
        reasons.append(f"no shared availability ({_fmt(giver.availability)} vs {_fmt(receiver.availability)})")

    return reasons


def meeting_mode(offer: Listing, need: Listing) -> str:
    remote_ok = offer.mode in ("remote", "either") and need.mode in ("remote", "either")
    in_person_ok = offer.mode in ("in_person", "either") and need.mode in ("in_person", "either")
    if remote_ok and in_person_ok:
        return "remote or in person"
    return "remote" if remote_ok else "in person"


def _fmt(slots) -> str:
    return ", ".join(sorted(s.replace("_", " ") for s in slots)) or "none listed"
