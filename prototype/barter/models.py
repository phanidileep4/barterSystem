"""Plain data types for the matching prototype. See docs/design/domain-model.md."""

import json
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


@dataclass(frozen=True)
class Listing:
    id: str
    owner_id: str
    kind: str  # "offer" or "need"
    text: str
    mode: str = "either"  # "in_person", "remote" or "either"
    effort_hours: Optional[float] = None
    # How the listing was understood, if already known (e.g. stored by an app,
    # extracted by an AI step, or corrected by its owner). None = use the dictionary.
    concepts: Optional[FrozenSet[str]] = None


@dataclass(frozen=True)
class Participant:
    id: str
    name: str
    zone: str
    max_travel: int
    availability: FrozenSet[str]
    offers: Tuple[Listing, ...]
    needs: Tuple[Listing, ...]
    blocks: FrozenSet[str] = frozenset()


@dataclass
class Community:
    participants: Dict[str, Participant]
    zones: Dict[str, List[str]] = field(default_factory=dict)

    def zone_distance(self, a: str, b: str) -> Optional[int]:
        """Hops between zones, or None if they are not connected."""
        if a == b:
            return 0
        seen, frontier, hops = {a}, [a], 0
        while frontier:
            hops += 1
            nxt = []
            for zone in frontier:
                for neighbour in self.zones.get(zone, []):
                    if neighbour == b:
                        return hops
                    if neighbour not in seen:
                        seen.add(neighbour)
                        nxt.append(neighbour)
            frontier = nxt
        return None


def _listings(raw: dict, owner_id: str, kind: str) -> Tuple[Listing, ...]:
    return tuple(
        Listing(
            id=item["id"],
            owner_id=owner_id,
            kind=kind,
            text=item["text"],
            mode=item.get("mode", "either"),
            effort_hours=item.get("effort_hours"),
        )
        for item in raw.get(kind + "s", [])
    )


def load_community(path: str) -> Community:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    participants = {}
    for raw in data["participants"]:
        pid = raw["id"]
        participants[pid] = Participant(
            id=pid,
            name=raw["name"],
            zone=raw["zone"],
            max_travel=raw.get("max_travel", 0),
            availability=frozenset(raw.get("availability", [])),
            offers=_listings(raw, pid, "offer"),
            needs=_listings(raw, pid, "need"),
            blocks=frozenset(raw.get("blocks", [])),
        )
    return Community(participants=participants, zones=data.get("zones", {}))
