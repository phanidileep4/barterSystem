# Proof of concept: one community, explained circles

A small web app that puts the [matching engine](../prototype/) in front of people and tests the question from the project's [vision](../docs/VISION.md):

> Can people **understand** the match, **refuse** it freely, **protect their privacy**, **resolve a problem**, and **leave the exchange better off**?

Each part of that sentence is a test in [tests/test_flow.py](tests/test_flow.py).

## Run it

Requires [uv](https://docs.astral.sh/uv/). It fetches Python 3.10+ and the dependencies on first run.

```bash
cd poc
uv run barter-poc
```

Open http://localhost:8000. The page loads Maple Commons, a fictional neighbourhood of 14 people. Use **Viewing as** to switch between them and walk a circle from each side. **Reset demo** restores the starting data.

```bash
uv run pytest
```

### With Claude (optional)

```bash
uv sync --extra claude
export ANTHROPIC_API_KEY=...        # or any credential the Anthropic SDK resolves
uv run barter-poc
```

The header chip switches to **Understanding: Claude**. Each listing is sent to Claude **once, when it is saved**: only the sentence itself, never a name, zone or history. Claude returns tags and reuses the community's existing vocabulary, so "Help positioning my small business online" and "Simple websites for small businesses" end up sharing tags. Without credentials, or if a call fails, the app uses the engine's word list instead.

| Setting | Default | |
|---|---|---|
| `BARTER_MODEL` | `claude-opus-5-5` | Model used for understanding (low effort; server-side refusal fallback enabled) |
| `BARTER_UNDERSTANDING` | auto | Set to `dictionary` to force the word list |
| `BARTER_DB` | `poc/data/barter-poc.sqlite3` | SQLite file, created and seeded on first run |
| `PORT` | `8000` | |

## Try this

1. **Asha → Chen → Ben.** As Asha, open the circle: why each link exists, a safety note for the teenager, uneven effort flagged. Accept. Switch to Chen and Ben and accept; it becomes **Agreed** only when all three have.
2. **Pass freely.** As anyone in a suggested circle, choose **Pass**. The others see that the circle didn't go ahead, never who passed, and it isn't suggested again.
3. **Near miss.** As Ivan, see under **Almost** that a dog walker in the East zone fits his need but is too far away, without being told who.
4. **The loop from the blog post.** As Marco, "Help positioning my small business online" finds nothing with the word list. In **My listings**, **Fix** it to `website, business, online`. A three-way circle with Dana and Priya appears. With Claude enabled, it appears without any fix.
5. **Ask for help.** In an agreed circle, **Ask a steward for help** pauses it.
6. **Finish.** When every receiver confirms, the circle completes: needs are marked fulfilled, and offers go back into the pool.

## How it's built

```
barter_poc/
  understanding.py   sentence → tags (word list, or Claude with fallback) + deterministic screen
  service.py         every state change; circle lifecycle; privacy rules
  db.py              SQLite schema (mirrors docs/design/domain-model.md)
  api.py             FastAPI routes + static page
  static/            index.html, app.js, styles.css (no build step)
  seed.json          the fictional community
```

Privacy rules live in `service.py`, not in the page: blocks are invisible, near misses don't name the other person, and pending circles show acceptance counts, never names.

## Deliberately not here yet

Sign-in (the participant id in each URL stands in for it), contact exchange after agreement, a steward console for reports and held listings, notifications, and deployment. Each one should follow evidence from trying this with real people.
