"""Plain-language explanations. Every suggestion must be able to say why."""

from typing import List

from .matcher import Circle, Result

IMBALANCE_RATIO = 2.0


def _hours(h) -> str:
    return "?" if h is None else f"~{h:g}h"


def explain_circle(circle: Circle, number: int) -> List[str]:
    n = len(circle.links)
    kind = "Direct swap" if n == 2 else f"Circle of {n}"
    names = " → ".join(p.name for p in circle.members) + f" → {circle.members[0].name}"
    out = [f"{kind} #{number} · confidence {circle.confidence:.2f}", f"  {names}", ""]

    for link in circle.links:
        out.append(f"  {link.giver.name} gives {link.receiver.name}: \"{link.offer.text}\"")
        out.append(f"      meets \"{link.need.text}\"")
        out.append(f"      shared: {', '.join(link.shared)} · {link.mode}")
        for note in link.safety_notes:
            out.append(f"      ⚠ {note}")

    out.append("")
    out.append("  Balance (self-declared effort):")
    for i, link in enumerate(circle.links):
        received = circle.links[i - 1].need  # the link before gives to this giver
        gives, gets = link.offer.effort_hours, received.effort_hours
        line = f"    {link.giver.name}: gives {_hours(gives)}, receives {_hours(gets)}"
        if gives and gets and max(gives, gets) / min(gives, gets) >= IMBALANCE_RATIO:
            line += "  ← uneven; worth agreeing scope together"
        out.append(line)
    everyone = "both" if n == 2 else f"all {n}"
    out.append(f"  Nothing starts unless {everyone} accept. Anyone can decline, no questions asked.")
    return out


def explain(result: Result) -> str:
    out = []
    if result.circles:
        for i, circle in enumerate(result.circles, 1):
            out += explain_circle(circle, i) + [""]
    else:
        out.append("No circles this round.\n")

    if result.near_misses:
        out.append("Near misses (an offer resembles a need, but a rule says no):")
        for m in result.near_misses:
            out.append(f"  {m.giver.name} → {m.receiver.name}: \"{m.offer.text}\" ≈ \"{m.need.text}\" ({m.score:.2f})")
            for reason in m.reasons:
                out.append(f"      ✗ {reason}")
            if m.would_swap:
                out.append("      ↺ the reverse also matches: relaxing this would create a direct swap")
        out.append("")

    if result.unserved:
        out.append("Needs not served this round:")
        for need, why in result.unserved:
            out.append(f"  \"{need.text}\" — {why}")
    return "\n".join(out)
