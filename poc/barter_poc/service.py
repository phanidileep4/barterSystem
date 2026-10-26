"""Every state change in the proof of concept goes through this module.

The circle lifecycle follows docs/design/domain-model.md:

    suggested --all accept--> agreed --every receiver confirms--> completed
        |                       |
        +--anyone passes--> dissolved      +--someone asks for help--> paused

Privacy rules enforced here, not in the UI:
- nobody learns who passed on a circle, or who blocked whom;
- near misses never name the other person;
- only counts of acceptances are shown while a circle is pending.
"""

import json
import os
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from barter.matcher import match
from barter.models import Community, Listing, Participant

from . import db as store

ZONES = {
    "north": ["central"],
    "central": ["north", "south", "east"],
    "south": ["central"],
    "east": ["central"],
}
SLOTS = ["weekday_morning", "weekday_evening", "weekend"]
MODES = ["either", "in_person", "remote"]
OPEN = ("suggested", "agreed", "paused")  # circles that reserve their listings
IMBALANCE_RATIO = 2.0

SEED = os.path.join(os.path.dirname(__file__), "seed.json")


class NotAllowed(Exception):
    """The request is understood but this participant may not do it."""


class Service:
    def __init__(self, conn: sqlite3.Connection, understander):
        self.conn = conn
        self.understander = understander

    # ------------------------------------------------------------------ setup

    def seed(self, path: str = SEED) -> None:
        store.reset(self.conn)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        pending = []
        for p in data["participants"]:
            self.conn.execute(
                "INSERT INTO participants VALUES (?, ?, ?, ?, ?)",
                (p["id"], p["name"], p["zone"], p.get("max_travel", 0), json.dumps(p.get("availability", []))),
            )
            for kind in ("offer", "need"):
                for item in p.get(kind + "s", []):
                    pending.append((item["id"], p["id"], kind, item))
            for blocked in p.get("blocks", []):
                self.conn.execute("INSERT INTO blocks VALUES (?, ?)", (p["id"], blocked))

        # Understanding is independent per listing, so seed them in parallel.
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda job: self.understander.understand(job[2], job[3]["text"]), pending))
        for (lid, pid, kind, item), understood in zip(pending, results):
            self._insert_listing(lid, pid, kind, item["text"], item.get("mode", "either"),
                                 item.get("effort_hours"), understood)
        self.conn.commit()
        self.run_matching()

    def is_empty(self) -> bool:
        return self.conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0] == 0

    # ------------------------------------------------------------ participants

    def participants(self) -> List[dict]:
        rows = self.conn.execute("SELECT id, name, zone FROM participants ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def _participant_row(self, pid: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM participants WHERE id = ?", (pid,)).fetchone()
        if row is None:
            raise KeyError(pid)
        return row

    def join(self, name: str, zone: str, max_travel: int, availability: List[str]) -> str:
        self._validate_profile(zone, max_travel, availability)
        if not name.strip():
            raise ValueError("name is required")
        pid = "p-" + uuid.uuid4().hex[:8]
        self.conn.execute("INSERT INTO participants VALUES (?, ?, ?, ?, ?)",
                          (pid, name.strip()[:60], zone, max_travel, json.dumps(availability)))
        self.conn.commit()
        return pid

    def update_profile(self, pid: str, zone: str, max_travel: int, availability: List[str]) -> None:
        self._participant_row(pid)
        self._validate_profile(zone, max_travel, availability)
        self.conn.execute("UPDATE participants SET zone = ?, max_travel = ?, availability = ? WHERE id = ?",
                          (zone, max_travel, json.dumps(availability), pid))
        self.conn.commit()
        self.run_matching()

    @staticmethod
    def _validate_profile(zone, max_travel, availability):
        if zone not in ZONES:
            raise ValueError(f"zone must be one of {sorted(ZONES)}")
        if not 0 <= max_travel <= 3:
            raise ValueError("max_travel must be between 0 and 3")
        if not set(availability) <= set(SLOTS):
            raise ValueError(f"availability must be drawn from {SLOTS}")

    # ---------------------------------------------------------------- listings

    def vocabulary(self) -> set:
        vocab = set()
        for (concepts,) in self.conn.execute("SELECT concepts FROM listings WHERE status = 'active'"):
            vocab.update(store.loads(concepts))
        return vocab

    def _insert_listing(self, lid, pid, kind, text, mode, effort, understood):
        status = "held" if understood.hold_reason else "active"
        self.conn.execute(
            "INSERT INTO listings (id, participant_id, kind, text, mode, effort_hours, concepts,"
            " concepts_source, status, held_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lid, pid, kind, text, mode, effort, store.dumps(understood.concepts),
             understood.source, status, understood.hold_reason),
        )

    def add_listing(self, pid: str, kind: str, text: str, mode: str = "either",
                    effort_hours: Optional[float] = None) -> str:
        self._participant_row(pid)
        text = text.strip()
        if kind not in ("offer", "need"):
            raise ValueError("kind must be offer or need")
        if not 3 <= len(text) <= 200:
            raise ValueError("describe it in 3 to 200 characters")
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        understood = self.understander.understand(kind, text, self.vocabulary())
        lid = "l-" + uuid.uuid4().hex[:8]
        self._insert_listing(lid, pid, kind, text, mode, effort_hours, understood)
        self.conn.commit()
        self.run_matching()
        return lid

    def _own_listing(self, pid: str, lid: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM listings WHERE id = ?", (lid,)).fetchone()
        if row is None:
            raise KeyError(lid)
        if row["participant_id"] != pid:
            raise NotAllowed("only the owner can change a listing")
        return row

    def edit_concepts(self, pid: str, lid: str, concepts: List[str]) -> None:
        """The owner corrects how they were understood. Their words win."""
        self._own_listing(pid, lid)
        cleaned = sorted({c.strip().lower()[:40] for c in concepts if c.strip()})[:12]
        if not cleaned:
            raise ValueError("keep at least one concept")
        self.conn.execute("UPDATE listings SET concepts = ?, concepts_source = 'edited' WHERE id = ?",
                          (store.dumps(cleaned), lid))
        self._dissolve_suggested(listing_id=lid)
        self.conn.commit()
        self.run_matching()

    def close_listing(self, pid: str, lid: str) -> None:
        self._own_listing(pid, lid)
        if self._circle_ids_for_listing(lid, ("agreed", "paused")):
            raise NotAllowed("this listing is part of an agreed circle; ask for help instead")
        self.conn.execute("UPDATE listings SET status = 'closed' WHERE id = ?", (lid,))
        self._dissolve_suggested(listing_id=lid)
        self.conn.commit()
        self.run_matching()

    # ---------------------------------------------------------------- matching

    def _reserved_listing_ids(self) -> set:
        rows = self.conn.execute(
            f"SELECT l.offer_id, l.need_id FROM links l JOIN circles c ON c.id = l.circle_id"
            f" WHERE c.status IN ({','.join('?' * len(OPEN))})", OPEN).fetchall()
        return {r[0] for r in rows} | {r[1] for r in rows}

    def _community(self) -> Community:
        reserved = self._reserved_listing_ids()
        listings: Dict[str, Dict[str, list]] = {}
        for r in self.conn.execute("SELECT * FROM listings WHERE status = 'active'"):
            if r["id"] in reserved:
                continue
            listing = Listing(r["id"], r["participant_id"], r["kind"], r["text"], r["mode"],
                              r["effort_hours"], frozenset(store.loads(r["concepts"])))
            listings.setdefault(r["participant_id"], {"offer": [], "need": []})[r["kind"]].append(listing)
        blocks: Dict[str, set] = {}
        for r in self.conn.execute("SELECT blocker_id, blocked_id FROM blocks"):
            blocks.setdefault(r[0], set()).add(r[1])
        people = {}
        for r in self.conn.execute("SELECT * FROM participants"):
            mine = listings.get(r["id"], {"offer": [], "need": []})
            people[r["id"]] = Participant(
                r["id"], r["name"], r["zone"], r["max_travel"], frozenset(store.loads(r["availability"])),
                tuple(mine["offer"]), tuple(mine["need"]), frozenset(blocks.get(r["id"], ())))
        return Community(people, ZONES)

    def _declined_signatures(self) -> frozenset:
        rows = self.conn.execute("SELECT signature FROM circles WHERE status = 'dissolved'").fetchall()
        return frozenset(frozenset(tuple(pair) for pair in json.loads(r[0])) for r in rows)

    def run_matching(self) -> int:
        """Suggest new circles among listings not already in an open circle."""
        result = match(self._community(), exclude=self._declined_signatures())
        for circle in result.circles:
            cur = self.conn.execute(
                "INSERT INTO circles (status, confidence, signature) VALUES ('suggested', ?, ?)",
                (circle.confidence, json.dumps(sorted(list(p) for p in circle.signature))))
            for i, link in enumerate(circle.links):
                self.conn.execute(
                    "INSERT INTO links (circle_id, position, giver_id, receiver_id, offer_id, need_id,"
                    " score, shared, mode, safety) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (cur.lastrowid, i, link.giver.id, link.receiver.id, link.offer.id, link.need.id,
                     link.score, store.dumps(list(link.shared)), link.mode, store.dumps(list(link.safety_notes))))
        self.conn.commit()
        return len(result.circles)

    # ----------------------------------------------------------------- circles

    def _circle(self, circle_id: int) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM circles WHERE id = ?", (circle_id,)).fetchone()
        if row is None:
            raise KeyError(circle_id)
        return row

    def _links(self, circle_id: int) -> List[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM links WHERE circle_id = ? ORDER BY position", (circle_id,)).fetchall()

    def _members(self, circle_id: int) -> List[str]:
        return [l["giver_id"] for l in self._links(circle_id)]

    def _require_member(self, pid: str, circle_id: int) -> sqlite3.Row:
        circle = self._circle(circle_id)
        if pid not in self._members(circle_id):
            raise NotAllowed("not a member of this circle")
        return circle

    def _set_status(self, circle_id: int, status: str) -> None:
        self.conn.execute("UPDATE circles SET status = ? WHERE id = ?", (status, circle_id))

    def _circle_ids_for_listing(self, lid: str, statuses) -> List[int]:
        rows = self.conn.execute(
            f"SELECT DISTINCT c.id FROM circles c JOIN links l ON l.circle_id = c.id"
            f" WHERE (l.offer_id = ? OR l.need_id = ?) AND c.status IN ({','.join('?' * len(statuses))})",
            (lid, lid, *statuses)).fetchall()
        return [r[0] for r in rows]

    def _dissolve_suggested(self, listing_id: Optional[str] = None, pair: Optional[tuple] = None) -> None:
        if listing_id:
            for cid in self._circle_ids_for_listing(listing_id, ("suggested",)):
                self._set_status(cid, "dissolved")
        if pair:
            for (cid,) in self.conn.execute("SELECT id FROM circles WHERE status IN ('suggested', 'agreed')").fetchall():
                members = set(self._members(cid))
                if set(pair) <= members:
                    status = self._circle(cid)["status"]
                    # An agreed circle needs a person to sort it out, not a silent dissolve.
                    self._set_status(cid, "dissolved" if status == "suggested" else "paused")

    def respond(self, pid: str, circle_id: int, response: str) -> str:
        circle = self._require_member(pid, circle_id)
        if circle["status"] != "suggested":
            raise NotAllowed(f"this circle is {circle['status']}")
        if response not in ("accepted", "declined"):
            raise ValueError("response must be accepted or declined")
        self.conn.execute("INSERT OR REPLACE INTO responses VALUES (?, ?, ?)", (circle_id, pid, response))
        if response == "declined":
            self._set_status(circle_id, "dissolved")
        else:
            accepted = self.conn.execute(
                "SELECT COUNT(*) FROM responses WHERE circle_id = ? AND response = 'accepted'",
                (circle_id,)).fetchone()[0]
            if accepted == len(self._members(circle_id)):
                self._set_status(circle_id, "agreed")
        self.conn.commit()
        if response == "declined":
            self.run_matching()
        return self._circle(circle_id)["status"]

    def confirm_received(self, pid: str, circle_id: int, note: str = "") -> str:
        circle = self._require_member(pid, circle_id)
        if circle["status"] != "agreed":
            raise NotAllowed("confirm once everyone has agreed")
        self.conn.execute("UPDATE links SET received = 1, note = ? WHERE circle_id = ? AND receiver_id = ?",
                          (note.strip()[:500] or None, circle_id, pid))
        links = self._links(circle_id)
        if all(l["received"] for l in links):
            self._set_status(circle_id, "completed")
            # Needs are met; offers (skills, time) go back into the pool.
            for l in links:
                self.conn.execute("UPDATE listings SET status = 'fulfilled' WHERE id = ?", (l["need_id"],))
        self.conn.commit()
        if self._circle(circle_id)["status"] == "completed":
            self.run_matching()
        return self._circle(circle_id)["status"]

    def report(self, pid: str, reason: str, circle_id: Optional[int] = None) -> None:
        if not reason.strip():
            raise ValueError("tell the steward what happened")
        if circle_id is not None:
            circle = self._require_member(pid, circle_id)
            if circle["status"] in ("suggested", "agreed"):
                self._set_status(circle_id, "paused")
        self.conn.execute("INSERT INTO reports (reporter_id, circle_id, reason) VALUES (?, ?, ?)",
                          (pid, circle_id, reason.strip()[:1000]))
        self.conn.commit()

    def block(self, pid: str, other_id: str) -> None:
        self._participant_row(pid)
        self._participant_row(other_id)
        if pid == other_id:
            raise ValueError("you cannot block yourself")
        self.conn.execute("INSERT OR IGNORE INTO blocks VALUES (?, ?)", (pid, other_id))
        self._dissolve_suggested(pair=(pid, other_id))
        self.conn.commit()
        self.run_matching()

    # ------------------------------------------------------------------- views

    def _blocked_either_way(self, pid: str) -> set:
        rows = self.conn.execute("SELECT blocker_id, blocked_id FROM blocks WHERE blocker_id = ? OR blocked_id = ?",
                                 (pid, pid)).fetchall()
        return {r[1] if r[0] == pid else r[0] for r in rows}

    def _circle_view(self, pid: str, circle: sqlite3.Row) -> dict:
        links = self._links(circle["id"])
        names = dict(self.conn.execute("SELECT id, name FROM participants").fetchall())
        listing = {r["id"]: r for r in self.conn.execute(
            f"SELECT * FROM listings WHERE id IN ({','.join('?' * len(links) * 2)})",
            [x for l in links for x in (l["offer_id"], l["need_id"])])}
        responses = dict(self.conn.execute(
            "SELECT participant_id, response FROM responses WHERE circle_id = ?", (circle["id"],)).fetchall())

        balance = []
        for i, l in enumerate(links):
            gives = listing[l["offer_id"]]["effort_hours"]
            gets = listing[links[i - 1]["need_id"]]["effort_hours"]
            uneven = bool(gives and gets and max(gives, gets) / min(gives, gets) >= IMBALANCE_RATIO)
            balance.append({"name": names[l["giver_id"]], "is_me": l["giver_id"] == pid,
                            "gives": gives, "receives": gets, "uneven": uneven})

        my_link_in = next((l for l in links if l["receiver_id"] == pid), None)
        status = circle["status"]
        return {
            "id": circle["id"],
            "status": status,
            "confidence": circle["confidence"],
            "members": [{"id": l["giver_id"], "name": names[l["giver_id"]], "is_me": l["giver_id"] == pid}
                        for l in links],
            "links": [{
                "giver": names[l["giver_id"]], "receiver": names[l["receiver_id"]],
                "giver_is_me": l["giver_id"] == pid, "receiver_is_me": l["receiver_id"] == pid,
                "offer": listing[l["offer_id"]]["text"], "need": listing[l["need_id"]]["text"],
                "shared": store.loads(l["shared"]), "mode": l["mode"],
                "safety": store.loads(l["safety"]), "received": bool(l["received"]),
            } for l in links],
            "balance": balance,
            # Counts only: who has or hasn't answered stays private.
            "accepted_count": sum(1 for r in responses.values() if r == "accepted"),
            "my_response": responses.get(pid),
            "can_respond": status == "suggested" and pid not in responses,
            "can_confirm": status == "agreed" and my_link_in is not None and not my_link_in["received"],
            "i_confirmed": bool(my_link_in and my_link_in["received"]),
            "received_count": sum(1 for l in links if l["received"]),
        }

    def _near_misses_for(self, pid: str, result) -> List[dict]:
        out = []
        for m in result.near_misses:
            if pid not in (m.giver.id, m.receiver.id):
                continue
            me, them = (m.receiver, m.giver) if m.receiver.id == pid else (m.giver, m.receiver)
            out.append({
                "direction": "they_could_help_me" if m.receiver.id == pid else "i_could_help_them",
                "my_text": m.need.text if m.receiver.id == pid else m.offer.text,
                "their_text": m.offer.text if m.receiver.id == pid else m.need.text,
                "their_zone": them.zone,
                "reasons": _anonymous_reasons(me, them, m),
                "would_swap": m.would_swap,
            })
        return out

    def dashboard(self, pid: str) -> dict:
        me = self._participant_row(pid)
        result = match(self._community(), exclude=self._declined_signatures())

        circle_rows = self.conn.execute(
            "SELECT DISTINCT c.* FROM circles c JOIN links l ON l.circle_id = c.id"
            " WHERE l.giver_id = ? ORDER BY c.id DESC", (pid,)).fetchall()
        open_circles = [c for c in circle_rows if c["status"] in OPEN]
        past = [c for c in circle_rows if c["status"] not in OPEN][:6]

        in_circle = {}
        for c in open_circles:
            for l in self._links(c["id"]):
                in_circle.setdefault(l["offer_id"], c["id"])
                in_circle.setdefault(l["need_id"], c["id"])

        listings = [{
            "id": r["id"], "kind": r["kind"], "text": r["text"], "mode": r["mode"],
            "effort_hours": r["effort_hours"], "concepts": store.loads(r["concepts"]),
            "concepts_source": r["concepts_source"], "status": r["status"],
            "held_reason": r["held_reason"], "circle_id": in_circle.get(r["id"]),
        } for r in self.conn.execute(
            "SELECT * FROM listings WHERE participant_id = ? AND status != 'closed' ORDER BY kind DESC, rowid",
            (pid,))]

        return {
            "me": {"id": me["id"], "name": me["name"], "zone": me["zone"], "max_travel": me["max_travel"],
                   "availability": store.loads(me["availability"])},
            "circles": [self._circle_view(pid, c) for c in open_circles],
            "past_circles": [self._circle_view(pid, c) for c in past],
            "listings": listings,
            "near_misses": self._near_misses_for(pid, result),
            "unserved": [{"text": need.text, "why": why} for need, why in result.unserved if need.owner_id == pid],
            "blocked": [dict(r) for r in self.conn.execute(
                "SELECT p.id, p.name FROM blocks b JOIN participants p ON p.id = b.blocked_id"
                " WHERE b.blocker_id = ? ORDER BY p.name", (pid,))],
        }

    def community_listings(self, pid: str) -> List[dict]:
        self._participant_row(pid)
        hidden = self._blocked_either_way(pid) | {pid}
        rows = self.conn.execute(
            "SELECT l.*, p.name, p.zone FROM listings l JOIN participants p ON p.id = l.participant_id"
            " WHERE l.status = 'active' ORDER BY p.name, l.kind DESC").fetchall()
        return [{"id": r["id"], "kind": r["kind"], "text": r["text"], "mode": r["mode"],
                 "owner_id": r["participant_id"], "owner": r["name"], "zone": r["zone"],
                 "concepts": store.loads(r["concepts"])}
                for r in rows if r["participant_id"] not in hidden]

    def status(self) -> dict:
        counts = dict(self.conn.execute("SELECT status, COUNT(*) FROM circles GROUP BY status").fetchall())
        return {
            "understanding": self.understander.name,
            "participants": self.conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0],
            "active_listings": self.conn.execute("SELECT COUNT(*) FROM listings WHERE status = 'active'").fetchone()[0],
            "circles": counts,
            "zones": list(ZONES), "slots": SLOTS, "modes": MODES,
        }


def _anonymous_reasons(me: Participant, them: Participant, miss) -> List[str]:
    """Rebuild the constraint reasons without naming the other person."""
    community = Community({}, ZONES)
    reasons = []
    offer, need = miss.offer, miss.need
    remote_ok = offer.mode in ("remote", "either") and need.mode in ("remote", "either")
    in_person_ok = offer.mode in ("in_person", "either") and need.mode in ("in_person", "either")
    if not remote_ok and not in_person_ok:
        reasons.append("one side is remote only and the other in person only")
    elif not remote_ok:
        distance = community.zone_distance(me.zone, them.zone)
        reach = max(me.max_travel, them.max_travel)
        if distance is None or distance > reach:
            reason = (f"you're {distance} zones apart ({me.zone} and {them.zone}) and the furthest "
                      f"either of you travels is {reach}")
            if distance == reach + 1:
                reason += "; one more zone of travel would connect you"
            reasons.append(reason)
    if not me.availability & them.availability:
        mine = ", ".join(s.replace("_", " ") for s in sorted(me.availability)) or "no times"
        theirs = ", ".join(s.replace("_", " ") for s in sorted(them.availability)) or "no times"
        reasons.append(f"no shared time: you're free {mine}; they're free {theirs}")
    return reasons
