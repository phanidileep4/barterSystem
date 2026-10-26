# Exchange scenarios

Five fictional scenarios for [issue #2](https://github.com/phanidileep4/barterSystem/issues/2). Names and details are invented. Scenarios 1, 2, 3 and 5 are encoded in the prototype's synthetic dataset ([prototype/data/maple_commons.json](../../prototype/data/maple_commons.json)).

---

## 1. The three-way circle (skills)

**Participants.** Asha teaches maths; Ben does small plumbing jobs; Chen is a portrait photographer.
**Offers → needs.** Asha needs a leaking faucet fixed. Ben needs a professional headshot. Chen needs maths tutoring for a teenage son.
**Why not a marketplace.** No pair wants each other's skill, so direct swaps fail. Each could pay, but all three have time to spare and money to save.
**Constraints.** Weekend and evening availability; plumbing is in person; tutoring involves a minor.
**What could go wrong.** One person drops out and the others feel abandoned; the tutoring arrangement is unsafe for the child; effort is lopsided (four tutoring sessions vs. one faucet).
**Success.** All three accept, each exchange completes, and the tutoring happens remotely or with a guardian present.

## 2. The direct swap (remote knowledge)

**Participants.** Diego, a Spanish speaker; Elif, a career coach.
**Offers → needs.** Diego wants resume feedback; Elif wants Spanish practice before a trip.
**Why not a marketplace.** Classic two-way swap, but they would never find each other on separate platforms, and neither wants to set a price.
**Constraints.** Both remote, both free on weekday evenings.
**What could go wrong.** Uneven quality expectations; one side delivers and the other ghosts.
**Success.** A bounded agreement ("three 45-minute conversations for one resume review") that both mark complete.

## 3. Neighbours during a move (goods and labour)

**Participants.** Farah is moving flats; Gus is strong and free at weekends; Hana repairs bikes and is overwhelmed with exams.
**Offers → needs.** Farah cooks a week of dinners for Hana; Hana tunes Gus's bike; Gus helps Farah move.
**Why not a marketplace.** Moving help from strangers is a trust problem; cooked meals are hard to buy from a neighbour.
**Constraints.** All in person in the same zone; food allergies; heavy lifting carries injury risk.
**What could go wrong.** Food safety; an injury during the move; the circle stalls because Hana's need is time-sensitive.
**Success.** The move happens, the meals arrive during exams, and the bike is ready for spring.

## 4. The newcomer (skills for local knowledge)

**Participants.** A recently arrived nurse who is waiting for credential recognition; a retired local who wants to learn to cook their spouse's regional cuisine.
**Offers → needs.** The newcomer offers cooking lessons and needs help with forms, local bureaucracy, and conversation practice.
**Why not a marketplace.** The newcomer has little local income and no network; the help they need is relational, not transactional.
**Constraints.** Language barriers; sensitive personal documents (the system must never see them).
**What could go wrong.** Exploitation of someone in a vulnerable position; sharing identity documents with a stranger.
**Success.** The newcomer gains a local ally; the system never stores or sends personal documents. *Not yet in the prototype — it needs a "sensitive topic" policy first.*

## 5. The near miss (constraints matter)

**Participants.** Ivan teaches piano and needs a dog walker; Jo walks dogs and wants piano lessons for a daughter.
**Offers → needs.** A perfect direct swap on paper.
**Why it fails.** Ivan lives in the North zone and cannot travel; Jo lives in the East. Both need in-person exchanges.
**What the system should do.** Not silently drop it. Explain the near miss: "a direct swap is possible if either of you can travel one more zone." The decision stays with them.
**Success.** Users understand why no circle was offered and what they could change.

---

## Patterns across scenarios

- Circles of three appear naturally once a dozen people list offers and needs.
- **Effort balance** is the most likely source of friction; it must be visible, not enforced.
- **Safety context** (minors, homes, food, physical labour) shows up in four of five scenarios — it is core, not an edge case.
- **Explaining failures** is as valuable as suggesting matches.
