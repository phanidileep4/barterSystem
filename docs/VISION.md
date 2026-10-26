# Vision: exchange circles

> Money solved barter's hardest problem by becoming a universal middle step.
> BarterSystem asks whether a matching engine can solve it another way: by finding the circle.

## The problem, stated precisely

Barter has always failed for the same reason: the *double coincidence of wants*. I can fix your bike, you need your bike fixed, but I need a photographer, not a cyclist. Money removes that requirement. Without money, the exchange stalls.

Earlier attempts to revive non-monetary exchange — time banks, local exchange trading systems, skill-swap boards — usually did not fail on values. They failed on **liquidity and coordination**: too few matches, too much effort to find them, and too much awkwardness negotiating fairness.

Those are exactly the problems modern software and AI can reduce.

## The core idea: circles, not markets

If Asha can tutor, Ben can fix plumbing, and Chen can take photos, then no two of them may want each other's skills, yet all three can be served:

```
Asha ──tutoring──▶ Chen ──headshot──▶ Ben ──plumbing──▶ Asha
```

This is the same insight behind **kidney paired donation**, where incompatible donor–patient pairs are matched in cycles, work recognised in the 2012 Nobel Prize in Economics. Those programs learned lessons BarterSystem should adopt from day one:

- **Keep circles short.** Every extra person is another chance for the circle to break. Prefer pairs, then threes; rarely fours.
- **All or nothing.** A circle only starts when every member accepts. If one person declines, nobody is left owing anyone; the engine simply looks again.
- **Re-match quickly.** A broken circle is normal, not a failure.

## Design pillars

1. **Need-first and in plain language.** People write "someone to fix a leaking kitchen faucet", not pick from a taxonomy. AI translates language into concepts; it never decides.
2. **Every suggestion explains itself.** Which words connected the offer to the need, which constraints were checked, and what is uncertain. No hidden scores.
3. **Fairness is declared, not computed.** The system shows each person's self-declared effort ("you give ~2h, you receive ~1h") and invites a conversation when it is lopsided. It never prices a person or their skill.
4. **Trust grows in bounded places.** Start inside one real community — a neighbourhood, a campus, a newcomer network — where people already share some context. Reputation stays contextual ("completed 3 exchanges in Maple Commons"), never a global social score.
5. **Safety is a feature, not a later phase.** Blocks are honoured silently and never revealed. Exchanges involving children, homes, or vehicles carry visible guidance. Reports go to humans.
6. **Privacy by architecture.** Matching uses coarse zones, not addresses. The AI step sees listing text only — never contact details, exact location, or history.

## Who this is for

The people for whom "just pay for it" is hardest or least meaningful:

- **Newcomers** to a city or country who have skills but not yet local income or networks.
- **Students and retirees**, rich in time and knowledge, short on money.
- **Small towns and neighbourhoods** where services are scarce but skills are not.
- **Communities after disruption** — job loss, disaster recovery — when cash is tight and help is everywhere.

And just as important, who it must **not** harm: workers whose paid labour could be undercut, people pressured into unsafe exchanges, and anyone the system might quietly rank. The boundaries in [CONTRIBUTING.md](../CONTRIBUTING.md) exist for them.

## How it fits together

```
 plain-language listings
          │
          ▼
 1. Understand   text → concepts (dictionary today, Claude later; always inspectable)
          │
          ▼
 2. Constrain    hard rules: blocks, mode, distance, availability     ← deterministic, never AI
          │
          ▼
 3. Connect      directed graph: edge A→B when A's offer meets B's need
          │
          ▼
 4. Find circles bounded cycle search (length 2–4), prefer short and confident
          │
          ▼
 5. Explain      why each link exists, balance of effort, safety notes, near misses
          │
          ▼
 6. People decide  propose → all accept → exchange → feedback   (or decline → re-match)
```

Separating step 2 from steps 1 and 3 is deliberate: a language model can widen *what counts as similar*, but it can never override *who is allowed to be matched*.

## Taking it further, in order

| Stage | What gets built | Evidence that it worked |
|---|---|---|
| **Now** | Prototype engine on synthetic data ([prototype/](../prototype/)), scenarios, domain model | Circles that a human reviewer agrees make sense; rejections that feel fair |
| **Next** | [Proof of concept](../poc/): a small web app with listings, explained circles, accept/pass, blocking, help, completion, and optional Claude-assisted understanding that falls back to the dictionary | One full exchange completed end-to-end in a usability test; better recall on varied phrasing without new false matches |
| **Pilot** | One invited community of 30–100 people | Completed circles, time-to-agreement, drop-out reasons, safety incidents (target: none unhandled) |
| **Later, if earned** | Optional *open loops* via community mutual credit, so a gift today can be returned by someone else next month | Pilot shows circles alone leave too many needs unmet |

Mutual credit is intentionally last. It is powerful, but it turns a matching tool into a ledger with real legal and tax weight. It should be adopted only when evidence demands it.

## What success looks like

Not scale. A neighbour gets a leaking tap fixed, a teenager passes maths, a newcomer gets the headshot that lands an interview — and three people who were strangers now know each other's names.
