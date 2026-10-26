# Matching prototype (proto-0.1)

A small, disposable spike for [issue #4](https://github.com/phanidileep4/barterSystem/issues/4): synthetic offers and needs in, **explained circles** out. It uses only the Python standard library (3.9+), with no network calls and no AI model yet.

## Run

```bash
cd prototype
python3 -m barter                       # uses data/maple_commons.json
python3 -m barter path/to/other.json    # your own synthetic community
python3 -m unittest discover -s tests
```

## What it does

| Step | Module | Notes |
|---|---|---|
| Understand | `barter/understand.py` | Words → concepts through an inspectable dictionary. Generic concepts ("help", "repair") count half and can never make a match on their own. Words about *who* (son, daughter, teen) never drive matching but trigger safety notes. |
| Constrain | `barter/constraints.py` | Deterministic, never AI: blocks, remote vs. in person, zone distance, shared availability. |
| Connect | `barter/matcher.py` | Edge A→B when A's offer covers ≥ 50% of B's need and every rule passes. |
| Find circles | `barter/matcher.py` | Every simple cycle of 2–4 people; confidence = mean match × 0.9 per extra member; greedy pick so nobody is asked twice. |
| Explain | `barter/explain.py` | Shared concepts, meeting mode, safety notes, self-declared effort balance, near misses and unserved needs. |

## What the sample data shows

From 11 fictional neighbours it finds a **direct swap** (Spanish ↔ resume review), and two **three-person circles** where no pair could have traded directly. It also shows:

- a **near miss** (piano ↔ dog walking) that fails only on distance, with a hint that relaxing it would create a swap;
- a **block** that makes two people invisible to each other, so nothing in the output reveals it;
- **uneven effort** flagged for conversation rather than "fixed" by pricing anyone;
- **safety notes** for a minor, food, and physical work.

## Known limits (on purpose)

- The concept dictionary is tiny and hand-written. Unknown phrasing will miss. That is the next experiment: Claude-assisted understanding behind the same `compare()` interface, with this dictionary kept as the fallback and test oracle.
- Greedy selection is not optimal. For larger communities, compare it with maximum-weight cycle packing (integer programming, as kidney exchanges use).
- One circle per person per round, and one offer and one need per link.
- Zones are a toy stand-in for coarse location.
