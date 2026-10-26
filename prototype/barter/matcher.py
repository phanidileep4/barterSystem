"""Steps 3–5 — Connect, find circles, explain.

Builds a directed graph (edge A -> B when one of A's offers meets one of B's
needs and passes every constraint), searches for short cycles, and picks a
set of circles in which nobody is asked to take part twice.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import constraints
from .models import Community, Listing, Participant
from .understand import compare, understand

MATCH_THRESHOLD = 0.5
MAX_CIRCLE = 4
# Each extra member is another chance for the circle to break.
LENGTH_PENALTY = 0.9


@dataclass(frozen=True)
class Link:
    giver: Participant
    receiver: Participant
    offer: Listing
    need: Listing
    score: float
    shared: Tuple[str, ...]
    mode: str
    safety_notes: Tuple[str, ...]


@dataclass
class Circle:
    links: List[Link]
    confidence: float

    @property
    def members(self) -> List[Participant]:
        return [link.giver for link in self.links]


@dataclass
class NearMiss:
    giver: Participant
    receiver: Participant
    offer: Listing
    need: Listing
    score: float
    reasons: List[str]
    # True when the reverse direction also has a match, so lifting this
    # constraint would create a direct swap.
    would_swap: bool = False


@dataclass
class Result:
    circles: List[Circle]
    near_misses: List[NearMiss]
    # need -> why it was not served this round
    unserved: List[Tuple[Listing, str]] = field(default_factory=list)


def _safety_notes(offer: Listing, need: Listing) -> Tuple[str, ...]:
    notes = []
    if understand(need.text).involves_minor or understand(offer.text).involves_minor:
        notes.append("Involves a minor: keep sessions remote or with a guardian present.")
    concepts = understand(offer.text).concepts | understand(need.text).concepts
    if "cooking" in concepts:
        notes.append("Food: share ingredients and check allergies first.")
    if "moving" in concepts:
        notes.append("Physical work: agree on limits and lift safely.")
    return tuple(notes)


def build_links(community: Community):
    """Best allowed link for every ordered pair, plus near misses that were ruled out."""
    links: Dict[Tuple[str, str], Link] = {}
    near_misses: List[NearMiss] = []
    people = list(community.participants.values())
    for giver in people:
        for receiver in people:
            if giver.id == receiver.id or constraints.is_blocked(giver, receiver):
                continue
            for offer in giver.offers:
                for need in receiver.needs:
                    score, shared = compare(offer.text, need.text)
                    if score < MATCH_THRESHOLD:
                        continue
                    reasons = constraints.check(community, giver, offer, receiver, need)
                    if reasons:
                        near_misses.append(NearMiss(giver, receiver, offer, need, score, reasons))
                        continue
                    key = (giver.id, receiver.id)
                    if key not in links or score > links[key].score:
                        links[key] = Link(
                            giver, receiver, offer, need, score,
                            tuple(sorted(shared)), constraints.meeting_mode(offer, need),
                            _safety_notes(offer, need),
                        )
    return links, near_misses


def find_cycles(links: Dict[Tuple[str, str], Link], max_len: int = MAX_CIRCLE) -> List[List[str]]:
    """All simple cycles up to max_len, each listed once (starting at its smallest id)."""
    graph: Dict[str, List[str]] = {}
    for giver_id, receiver_id in links:
        graph.setdefault(giver_id, []).append(receiver_id)

    cycles = []

    def walk(start: str, node: str, path: List[str]):
        for nxt in graph.get(node, []):
            if nxt == start and len(path) >= 2:
                cycles.append(list(path))
            elif nxt > start and nxt not in path and len(path) < max_len:
                walk(start, nxt, path + [nxt])

    for start in sorted(graph):
        walk(start, start, [start])
    return cycles


def match(community: Community) -> Result:
    links, near_misses = build_links(community)
    matched_pairs = {(m.giver.id, m.receiver.id) for m in near_misses} | set(links)
    for m in near_misses:
        m.would_swap = (m.receiver.id, m.giver.id) in matched_pairs

    candidates = []
    for cycle in find_cycles(links):
        circle_links = [links[(cycle[i], cycle[(i + 1) % len(cycle)])] for i in range(len(cycle))]
        mean = sum(l.score for l in circle_links) / len(circle_links)
        confidence = round(mean * LENGTH_PENALTY ** (len(cycle) - 2), 2)
        candidates.append(Circle(circle_links, confidence))

    # Greedy: most confident first, shorter on ties; nobody appears in two circles.
    candidates.sort(key=lambda c: (-c.confidence, len(c.links)))
    chosen, used = [], set()
    for circle in candidates:
        ids = {p.id for p in circle.members}
        if ids & used:
            continue
        chosen.append(circle)
        used |= ids

    served = {link.need.id for circle in chosen for link in circle.links}
    has_any_link = {key[1] for key in links}
    unserved = []
    for person in community.participants.values():
        for need in person.needs:
            if need.id in served:
                continue
            if any(m.need.id == need.id for m in near_misses):
                why = "similar offers exist but constraints ruled them out (see near misses)"
            elif person.id in has_any_link:
                why = "someone can help, but no circle closes back to them yet"
            else:
                why = "no current offer resembles this need"
            unserved.append((need, why))

    return Result(circles=chosen, near_misses=near_misses, unserved=unserved)
