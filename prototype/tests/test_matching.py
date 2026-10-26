import os
import unittest

from barter.explain import explain
from barter.matcher import match
from barter.models import Community, Listing, Participant, load_community
from barter.understand import compare, understand

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "maple_commons.json")


def person(pid, offer, need, zone="central", travel=1, slots=("weekend",), blocks=(), mode="either"):
    return Participant(
        id=pid, name=pid.title(), zone=zone, max_travel=travel, availability=frozenset(slots),
        offers=(Listing(pid + "-o", pid, "offer", offer, mode, 1),),
        needs=(Listing(pid + "-n", pid, "need", need, mode, 1),),
        blocks=frozenset(blocks),
    )


def community(*people):
    return Community({p.id: p for p in people}, {"north": ["central"], "central": ["north", "east"], "east": ["central"]})


class UnderstandTest(unittest.TestCase):
    def test_related_wording_matches(self):
        score, shared = compare("Career coaching and resume review", "Feedback on my resume")
        self.assertGreaterEqual(score, 0.5)
        self.assertEqual(shared, {"resume", "feedback"})

    def test_generic_overlap_alone_is_not_a_match(self):
        score, _ = compare("Help with gardening", "Help with taxes")
        self.assertEqual(score, 0.0)

    def test_minor_detected_but_not_used_for_matching(self):
        u = understand("Math tutoring for my teenage son")
        self.assertTrue(u.involves_minor)
        self.assertNotIn("son", u.concepts)


class MatchTest(unittest.TestCase):
    def test_sample_community_finds_expected_circles(self):
        result = match(load_community(DATA))
        circles = sorted(sorted(p.name for p in c.members) for c in result.circles)
        self.assertEqual(circles, [["Asha", "Ben", "Chen"], ["Diego", "Elif"], ["Farah", "Gus", "Hana"]])

    def test_three_way_circle_when_no_direct_swap_exists(self):
        c = community(
            person("a", "piano lessons", "bike repair"),
            person("b", "bike repair", "dog walking"),
            person("c", "dog walking", "piano lessons"),
        )
        result = match(c)
        self.assertEqual(len(result.circles), 1)
        self.assertEqual(len(result.circles[0].links), 3)

    def test_nobody_is_in_two_circles(self):
        c = community(
            person("a", "piano lessons", "bike repair"),
            person("b", "bike repair", "piano lessons"),
            person("c", "piano lessons", "bike repair"),
        )
        members = [p.id for circle in match(c).circles for p in circle.members]
        self.assertEqual(len(members), len(set(members)))

    def test_block_is_invisible_in_output(self):
        c = community(
            person("a", "piano lessons", "bike repair", blocks=("b",)),
            person("b", "bike repair", "piano lessons"),
        )
        result = match(c)
        self.assertEqual(result.circles, [])
        self.assertEqual(result.near_misses, [])
        text = explain(result)
        self.assertNotIn("block", text.lower())
        self.assertNotIn("boundary", text.lower())

    def test_distance_rule_becomes_explained_near_miss(self):
        c = community(
            person("a", "piano lessons", "bike repair", zone="north", travel=0, mode="in_person"),
            person("b", "bike repair", "piano lessons", zone="east", travel=1, mode="in_person"),
        )
        result = match(c)
        self.assertEqual(result.circles, [])
        self.assertEqual(len(result.near_misses), 2)
        self.assertTrue(all(m.would_swap for m in result.near_misses))
        self.assertIn("2 zones apart", result.near_misses[0].reasons[0])

    def test_remote_ignores_distance(self):
        c = community(
            person("a", "piano lessons", "bike repair", zone="north", travel=0, mode="remote"),
            person("b", "bike repair", "piano lessons", zone="east", travel=0, mode="remote"),
        )
        self.assertEqual(len(match(c).circles), 1)

    def test_no_shared_availability_is_explained(self):
        c = community(
            person("a", "piano lessons", "bike repair", slots=("weekday_morning",)),
            person("b", "bike repair", "piano lessons", slots=("weekend",)),
        )
        result = match(c)
        self.assertEqual(result.circles, [])
        self.assertIn("no shared availability", result.near_misses[0].reasons[0])

    def test_minor_gets_safety_note(self):
        result = match(load_community(DATA))
        notes = [n for c in result.circles for l in c.links for n in l.safety_notes]
        self.assertTrue(any("minor" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
