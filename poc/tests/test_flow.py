"""The test from the blog post, as code: can people understand a match, refuse it
freely, protect their privacy, resolve a problem, and leave better off?"""

import json

import pytest
from fastapi.testclient import TestClient

from barter_poc import db
from barter_poc.api import create_app
from barter_poc.service import NotAllowed, Service
from barter_poc.understanding import DictionaryUnderstanding, Understood


@pytest.fixture
def svc():
    s = Service(db.connect(":memory:"), DictionaryUnderstanding())
    s.seed()
    return s


def circle_of(svc, pid, *names):
    for c in svc.dashboard(pid)["circles"]:
        if sorted(m["name"] for m in c["members"]) == sorted(names):
            return c
    return None


def test_seed_suggests_the_expected_circles(svc):
    assert circle_of(svc, "p1", "Asha", "Ben", "Chen")["status"] == "suggested"
    assert circle_of(svc, "p4", "Diego", "Elif")
    assert circle_of(svc, "p6", "Farah", "Gus", "Hana")


def test_understand_every_link_explains_itself(svc):
    c = circle_of(svc, "p1", "Asha", "Ben", "Chen")
    for link in c["links"]:
        assert link["shared"] and link["mode"] and link["offer"] and link["need"]
    assert any("minor" in s for link in c["links"] for s in link["safety"])
    assert any(b["uneven"] for b in c["balance"])


def test_agreement_is_all_or_nothing(svc):
    cid = circle_of(svc, "p1", "Asha", "Ben", "Chen")["id"]
    assert svc.respond("p1", cid, "accepted") == "suggested"
    assert svc.respond("p3", cid, "accepted") == "suggested"
    view = circle_of(svc, "p2", "Asha", "Ben", "Chen")
    assert view["accepted_count"] == 2 and view["can_respond"]
    assert svc.respond("p2", cid, "accepted") == "agreed"


def test_refuse_freely_and_anonymously(svc):
    cid = circle_of(svc, "p1", "Asha", "Ben", "Chen")["id"]
    svc.respond("p1", cid, "accepted")
    svc.respond("p3", cid, "declined")
    past = svc.dashboard("p1")["past_circles"][0]
    assert past["status"] == "dissolved"
    # Asha cannot tell who passed: no per-person responses are exposed.
    assert "responses" not in past and all(set(m) == {"id", "name", "is_me"} for m in past["members"])
    # The same circle is never suggested again, and Asha's listings are free.
    assert circle_of(svc, "p1", "Asha", "Ben", "Chen") is None
    assert all(l["circle_id"] is None for l in svc.dashboard("p1")["listings"])


def test_privacy_blocks_are_invisible(svc):
    svc.block("p13", "p12")  # Priya blocks Dana
    for pid in ("p12", "p13"):
        text = json.dumps(svc.dashboard(pid))
        assert "block" not in text.replace('"blocked"', "")
    assert all(l["owner_id"] != "p13" for l in svc.community_listings("p12"))
    assert svc.dashboard("p12")["blocked"] == []  # Dana's own view shows no one


def test_privacy_near_misses_do_not_name_the_other_person(svc):
    misses = svc.dashboard("p9")["near_misses"]  # Ivan
    assert misses and all("Jo" not in json.dumps(m) for m in misses)
    assert any("zones apart" in r for m in misses for r in m["reasons"])
    assert all(m["would_swap"] for m in misses)


def test_blocking_mid_suggestion_withdraws_the_circle(svc):
    cid = circle_of(svc, "p1", "Asha", "Ben", "Chen")["id"]
    svc.block("p1", "p2")
    assert svc._circle(cid)["status"] == "dissolved"


def test_resolve_a_problem_pauses_the_circle(svc):
    cid = circle_of(svc, "p4", "Diego", "Elif")["id"]
    svc.respond("p4", cid, "accepted")
    svc.respond("p5", cid, "accepted")
    svc.report("p4", "Elif hasn't replied in two weeks", cid)
    assert svc._circle(cid)["status"] == "paused"
    with pytest.raises(NotAllowed):
        svc.confirm_received("p5", cid)


def test_leave_better_off_needs_fulfilled_offers_return(svc):
    cid = circle_of(svc, "p4", "Diego", "Elif")["id"]
    for pid in ("p4", "p5"):
        svc.respond(pid, cid, "accepted")
    assert svc.confirm_received("p4", cid, "Great feedback") == "agreed"
    assert svc.confirm_received("p5", cid) == "completed"
    statuses = {l["kind"]: l["status"] for l in svc.dashboard("p4")["listings"]}
    assert statuses == {"offer": "active", "need": "fulfilled"}


def test_owner_correction_closes_the_blog_loop(svc):
    # The word list can't see that "positioning my small business online" wants a website.
    assert circle_of(svc, "p14", "Dana", "Marco", "Priya") is None
    marco_need = next(l for l in svc.dashboard("p14")["listings"] if l["kind"] == "need")
    svc.edit_concepts("p14", marco_need["id"], ["website", "business", "online"])
    c = circle_of(svc, "p14", "Dana", "Marco", "Priya")
    assert c is not None
    assert next(l for l in c["links"] if l["receiver"] == "Marco")["shared"] == ["business", "website"]


def test_only_owners_change_listings(svc):
    lid = svc.dashboard("p1")["listings"][0]["id"]
    with pytest.raises(NotAllowed):
        svc.edit_concepts("p2", lid, ["anything"])
    with pytest.raises(NotAllowed):
        svc.respond("p9", circle_of(svc, "p1", "Asha", "Ben", "Chen")["id"], "accepted")


def test_screened_listing_is_held_not_matched(svc):
    lid = svc.add_listing("p11", "offer", "Quick cash loan for neighbours")
    listing = next(l for l in svc.dashboard("p11")["listings"] if l["id"] == lid)
    assert listing["status"] == "held" and "steward" in listing["held_reason"]


class FakeClaude:
    name = "claude"

    def understand(self, kind, text, vocabulary=()):
        tags = {"Help positioning my small business online": ["online presence", "website", "small business"],
                "Simple websites for small businesses": ["web design", "website", "small business", "online presence"]}
        return Understood(tags.get(text, sorted(DictionaryUnderstanding().understand(kind, text).concepts)), "claude")


def test_semantic_understanding_finds_the_loop_without_correction():
    s = Service(db.connect(":memory:"), FakeClaude())
    s.seed()
    assert circle_of(s, "p14", "Dana", "Marco", "Priya") is not None


def test_api_round_trip(svc):
    client = TestClient(create_app(svc))
    assert client.get("/api/status").json()["understanding"] == "dictionary"
    dash = client.get("/api/people/p1/dashboard").json()
    cid = dash["circles"][0]["id"]
    assert client.post(f"/api/people/p1/circles/{cid}/respond", json={"response": "accepted"}).status_code == 200
    assert client.post(f"/api/people/p9/circles/{cid}/respond", json={"response": "accepted"}).status_code == 403
    assert client.post("/api/people/p1/listings", json={"kind": "offer", "text": "x"}).status_code == 422
    assert client.get("/api/people/nobody/dashboard").status_code == 404
    assert "BarterSystem" in client.get("/").text


def test_claude_without_credentials_falls_back_to_word_list():
    pytest.importorskip("anthropic")
    from barter_poc.understanding import ClaudeUnderstanding

    class NoCredentials:
        class beta:
            class messages:
                @staticmethod
                def create(**_):
                    raise TypeError("Could not resolve authentication method")

    u = ClaudeUnderstanding(NoCredentials(), "claude-opus-5-5")
    result = u.understand("need", "Help preparing my taxes")
    assert result.source == "dictionary" and "tax" in result.concepts
    assert u.name == "dictionary"


def test_passcode_gate(svc):
    client = TestClient(create_app(svc, passcode="maple-2026"))
    assert client.get("/healthz").status_code == 200
    assert "Enter the passcode" in client.get("/").text
    assert client.get("/api/people").status_code == 401
    assert client.get("/static/app.js").status_code != 200
    assert client.get("/docs").status_code == 404 or "passcode" in client.get("/docs").text.lower()

    wrong = client.post("/unlock", data={"passcode": "guess"}, follow_redirects=False)
    assert wrong.status_code == 401 and "didn't work" in wrong.text
    assert client.get("/api/people").status_code == 401

    right = client.post("/unlock", data={"passcode": "maple-2026"}, follow_redirects=False)
    assert right.status_code == 303 and "httponly" in right.headers["set-cookie"].lower()
    assert client.get("/api/people").status_code == 200
    assert "Viewing as" in client.get("/").text


def test_no_passcode_means_open_for_local_use(svc):
    assert TestClient(create_app(svc)).get("/api/people").status_code == 200
