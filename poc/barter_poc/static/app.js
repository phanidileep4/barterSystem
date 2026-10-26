// BarterSystem POC page. Plain JS, no build step.
"use strict";

const state = { pid: null, tab: "circles", people: [], status: null, dash: null, community: [] };
const view = document.getElementById("view");

// ---------------------------------------------------------------- helpers

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const slot = (s) => s.replace("_", " ");
const hours = (h) => (h == null ? "?" : `${h}h`);
const MODE = { either: "remote or in person", in_person: "in person", remote: "remote" };
const SOURCE = { dictionary: "word list", claude: "Claude", edited: "you" };

function remember(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* storage unavailable */ } }
function recall(key) { try { return localStorage.getItem(key); } catch (_) { return null; } }

async function api(method, path, body) {
  const res = await fetch(path, {
    method, headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong");
  return data;
}

let toastTimer;
function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

async function act(fn, message) {
  try { await fn(); if (message) toast(message); await refresh(); }
  catch (e) { toast(e.message); }
}

// ------------------------------------------------------------------- data

async function loadPeople() {
  state.people = await api("GET", "/api/people");
  const saved = recall("pid");
  state.pid = state.people.some((p) => p.id === saved) ? saved : (state.people.find((p) => p.name === "Asha") || state.people[0])?.id;
  const sel = document.getElementById("persona");
  sel.innerHTML = state.people.map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.zone)}</option>`).join("");
  sel.value = state.pid;
}

async function refresh() {
  if (!state.pid) return;
  const [status, dash, community] = await Promise.all([
    api("GET", "/api/status"),
    api("GET", `/api/people/${state.pid}/dashboard`),
    api("GET", `/api/people/${state.pid}/community`),
  ]);
  Object.assign(state, { status, dash, community });
  const mode = document.getElementById("mode");
  mode.textContent = status.understanding === "claude" ? "Understanding: Claude" : "Understanding: word list";
  mode.className = "chip" + (status.understanding === "claude" ? " claude" : "");
  render();
}

// ------------------------------------------------------------------ rings

function ring(circle) {
  const n = circle.members.length, R = 72, C = 120, NODE = 21;
  const angle = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const pt = (a, r = R) => [C + r * Math.cos(a), C + r * Math.sin(a)];
  const gap = Math.asin((NODE + 6) / R);
  let arcs = "", nodes = "";
  circle.links.forEach((link, i) => {
    const a0 = angle(i) + gap, a1 = angle(i + 1) - gap;
    const [x0, y0] = pt(a0), [x1, y1] = pt(a1);
    const done = link.received ? " done" : "";
    arcs += `<path class="arc${done}" d="M${x0.toFixed(1)} ${y0.toFixed(1)} A${R} ${R} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}"/>`;
    // arrowhead tangent to the circle at the arc's end
    const t = a1 + Math.PI / 2, s = 7;
    const tip = [x1, y1];
    const back = [x1 - s * Math.cos(t), y1 - s * Math.sin(t)];
    const l = [back[0] + (s / 2) * Math.cos(a1), back[1] + (s / 2) * Math.sin(a1)];
    const r = [back[0] - (s / 2) * Math.cos(a1), back[1] - (s / 2) * Math.sin(a1)];
    arcs += `<polygon class="arrow${done}" points="${[tip, l, r].map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ")}"/>`;
  });
  circle.members.forEach((m, i) => {
    const [x, y] = pt(angle(i));
    const [lx, ly] = pt(angle(i), R + NODE + 14);
    const me = m.is_me ? " me" : "";
    nodes += `<circle class="node${me}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${NODE}"/>
      <text class="initial${me}" x="${x.toFixed(1)}" y="${y.toFixed(1)}">${esc(m.name[0])}</text>
      <text class="label" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}">${esc(m.is_me ? "You" : m.name)}</text>`;
  });
  const names = circle.members.map((m) => m.name).join(", then ");
  return `<svg class="ring" viewBox="0 0 240 240" role="img" aria-label="Circle: ${esc(names)}, back to the start">
    <circle class="track" cx="${C}" cy="${C}" r="${R}" fill="none" stroke-width="1"/>${arcs}${nodes}</svg>`;
}

// ---------------------------------------------------------------- circles

const STATUS_LABEL = { suggested: "Suggested", agreed: "Agreed", paused: "Paused", completed: "Completed", dissolved: "Didn't go ahead" };

function circleFoot(c) {
  const n = c.members.length, all = n === 2 ? "both of you" : `all ${n} of you`;
  if (c.status === "suggested") {
    if (c.can_respond) {
      return `<p>Nothing starts unless ${all} say yes. Passing is free, and no one is told who passed.</p>
        <div class="actions">
          <button class="primary" data-respond="accepted" data-cid="${c.id}">I'm in</button>
          <button class="secondary" data-respond="declined" data-cid="${c.id}">Pass</button>
        </div>`;
    }
    return `<p>You're in. ${c.accepted_count} of ${n} have said yes so far. It starts only when everyone has.</p>`;
  }
  if (c.status === "agreed") {
    const help = `<button class="ghost" data-help="${c.id}">Ask a steward for help</button>`;
    if (c.can_confirm) {
      return `<p>Everyone said yes. Arrange the details together, then confirm when you've received yours.</p>
        <div class="actions"><button class="primary" data-received="${c.id}">I've received mine</button>${help}</div>`;
    }
    return `<p>${c.i_confirmed ? "Thanks for confirming. " : ""}${c.received_count} of ${n} have confirmed so far.</p><div class="actions">${help}</div>`;
  }
  if (c.status === "paused") return `<p>Paused while a community steward helps. Nobody's record is affected.</p>`;
  if (c.status === "completed") return `<p>Completed. Your offers are back in the pool for the next circle.</p>`;
  return `<p>This circle didn't go ahead. No reason is shared, and your listings went back into the pool.</p>`;
}

function circleCard(c) {
  const n = c.members.length;
  const title = n === 2 ? "A direct swap" : `A circle of ${n}`;
  const links = c.links.map((l) => {
    const giver = l.giver_is_me ? "You" : esc(l.giver);
    const receiver = l.receiver_is_me ? "you" : esc(l.receiver);
    return `<li class="${l.received ? "done" : ""}">
      <span class="who">${giver} → ${receiver}${l.received ? " ✓" : ""}</span>
      <span class="quote">“${esc(l.offer)}”</span>
      <span class="why">for “${esc(l.need)}” · ${esc(l.mode)} · matched on ${l.shared.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</span>
      ${l.safety.map((s) => `<span class="safety">⚠ ${esc(s)}</span>`).join("")}
    </li>`;
  }).join("");
  const max = Math.max(1, ...c.balance.flatMap((b) => [b.gives || 0, b.receives || 0]));
  const balance = c.balance.map((b) => `<div class="bal">
      <span>${b.is_me ? "You" : esc(b.name)}</span>
      <span class="bars" aria-hidden="true">
        <span class="bar" style="width:${((b.gives || 0) / max) * 100}%"></span>
        <span class="bar in" style="width:${((b.receives || 0) / max) * 100}%"></span>
      </span>
      <span class="num">gives ${hours(b.gives)} · gets ${hours(b.receives)}</span>
    </div>${b.uneven ? `<div class="bal"><span></span><span class="note">Uneven. Worth agreeing on scope together.</span><span></span></div>` : ""}`).join("");
  return `<article class="card circle">
    ${ring(c)}
    <div>
      <div class="circle-head"><h2>${title}</h2><span class="pill ${c.status}">${STATUS_LABEL[c.status]}</span>
        <span class="confidence">match ${Math.round(c.confidence * 100)}%</span></div>
      <ul class="links">${links}</ul>
      <div class="balance"><h3>Effort, as each person described it</h3>${balance}</div>
      <div class="circle-foot">${circleFoot(c)}</div>
    </div>
  </article>`;
}

function renderCircles() {
  const d = state.dash;
  const open = d.circles.length
    ? d.circles.map(circleCard).join("")
    : `<div class="empty">No circle for you right now. Add an offer or a need, or widen your travel range in Profile.</div>`;
  const near = d.near_misses.map((m) => `<div class="card mini">
      <span class="kind ${m.direction === "they_could_help_me" ? "need" : "offer"}">${m.direction === "they_could_help_me" ? "Someone could help you" : "You could help someone"}</span>
      <p>“${esc(m.their_text)}” in ${esc(m.their_zone)} fits your “${esc(m.my_text)}”.</p>
      ${m.reasons.map((r) => `<p class="reason">✗ ${esc(r)}</p>`).join("")}
      ${m.would_swap ? `<p class="hint">↺ It works in reverse too, so this could become a direct swap.</p>` : ""}
    </div>`).join("");
  const waiting = d.unserved.map((u) => `<div class="card mini"><span class="kind need">Still looking</span><p>“${esc(u.text)}”</p><p class="reason">${esc(u.why)}</p></div>`).join("");
  const past = d.past_circles.length ? `<details class="past"><summary>Earlier circles (${d.past_circles.length})</summary><div class="section">${d.past_circles.map(circleCard).join("")}</div></details>` : "";

  view.innerHTML = `
    <section class="lede"><h1>Hi ${esc(d.me.name)}.</h1>
      <p>These are exchanges that could happen for you. Each one shows why it was suggested, and nothing happens unless everyone in it agrees.</p></section>
    <section class="section">${open}</section>
    ${near ? `<section class="section"><header><h2>Almost</h2><p>Someone fits, but a rule says no. The other person isn't named.</p></header><div class="grid">${near}</div></section>` : ""}
    ${waiting ? `<section class="section"><header><h2>Waiting</h2><p>If you were misunderstood, fix it in My listings.</p></header><div class="grid">${waiting}</div></section>` : ""}
    ${past}`;

  view.querySelectorAll("[data-respond]").forEach((b) => b.addEventListener("click", () => {
    const accepted = b.dataset.respond === "accepted";
    act(() => api("POST", `/api/people/${state.pid}/circles/${b.dataset.cid}/respond`, { response: b.dataset.respond }),
      accepted ? "You're in." : "Passed. No one will be told who.");
  }));
  view.querySelectorAll("[data-received]").forEach((b) => b.addEventListener("click", () => {
    const note = prompt("Anything to add? (optional, only for this circle)") ?? "";
    act(() => api("POST", `/api/people/${state.pid}/circles/${b.dataset.received}/received`, { note }), "Thanks for confirming.");
  }));
  view.querySelectorAll("[data-help]").forEach((b) => b.addEventListener("click", () => {
    const reason = prompt("What happened? A community steward will read this.");
    if (reason) act(() => api("POST", `/api/people/${state.pid}/reports`, { reason, circle_id: Number(b.dataset.help) }), "Circle paused. A steward will reach out.");
  }));
}

// --------------------------------------------------------------- listings

function listingCard(l) {
  const status = l.status === "held" ? `<p class="held">Held: ${esc(l.held_reason)}</p>`
    : l.status === "fulfilled" ? `<p class="meta">Fulfilled through a circle ✓</p>`
    : l.circle_id ? `<p class="meta">In a circle right now</p>` : "";
  return `<div class="card listing" data-lid="${esc(l.id)}">
    <div class="row between"><span class="kind ${l.kind}">${l.kind === "offer" ? "I can offer" : "I need"}</span>
      ${l.status !== "fulfilled" ? `<button class="link" data-close="${esc(l.id)}">Remove</button>` : ""}</div>
    <p class="text">${esc(l.text)}</p>
    <p class="meta">${esc(MODE[l.mode])} · about ${hours(l.effort_hours)}</p>
    <div class="understood">Understood as ${l.concepts.map((c) => `<span class="tag">${esc(c)}</span>`).join("")}
      <span>by ${esc(SOURCE[l.concepts_source] || l.concepts_source)}</span>
      ${l.status === "active" ? `<button class="link" data-edit="${esc(l.id)}">Fix</button>` : ""}</div>
    ${status}
  </div>`;
}

function renderListings() {
  const d = state.dash, s = state.status;
  view.innerHTML = `
    <section class="lede"><h1>What you offer and need</h1>
      <p>Write it the way you'd say it to a neighbour. You'll see exactly how it was understood, and you can fix it.</p></section>
    <section class="card">
      <form class="add" id="add">
        <div class="seg" role="radiogroup" aria-label="Kind">
          <label><input type="radio" name="kind" value="offer" checked><span>I can offer</span></label>
          <label><input type="radio" name="kind" value="need"><span>I need</span></label>
        </div>
        <textarea name="text" required minlength="3" maxlength="200" placeholder="e.g. Help positioning my small business online"></textarea>
        <div class="row">
          <label class="field"><span>How</span><select name="mode">${s.modes.map((m) => `<option value="${m}">${MODE[m]}</option>`).join("")}</select></label>
          <label class="field"><span>Effort (hours)</span><input type="number" name="effort" min="0" max="100" step="0.5" value="1" style="width:7em"></label>
          <button class="primary" type="submit" style="align-self:end">Add</button>
        </div>
        <p class="fineprint">${s.understanding === "claude"
          ? "Only this sentence is sent to Claude to understand it. Never your name, zone or history."
          : "Understood on this machine with a small word list. Set up Claude for better understanding (see README)."}</p>
      </form>
    </section>
    <section class="section"><div class="grid">${d.listings.map(listingCard).join("") || `<div class="empty">Nothing listed yet.</div>`}</div></section>`;

  document.getElementById("add").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const btn = e.target.querySelector("button[type=submit]");
    btn.disabled = true; btn.textContent = "Understanding…";
    act(() => api("POST", `/api/people/${state.pid}/listings`, {
      kind: f.get("kind"), text: f.get("text"), mode: f.get("mode"),
      effort_hours: f.get("effort") === "" ? null : Number(f.get("effort")),
    }), "Added. Looking for circles…");
  });
  view.querySelectorAll("[data-edit]").forEach((b) => b.addEventListener("click", () => {
    const l = d.listings.find((x) => x.id === b.dataset.edit);
    const next = prompt("Comma-separated words that describe this. Your words replace the automatic ones.", l.concepts.join(", "));
    if (next !== null) act(() => api("PUT", `/api/people/${state.pid}/listings/${l.id}/concepts`, { concepts: next.split(",") }), "Updated. Looking for circles…");
  }));
  view.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => {
    if (confirm("Remove this listing? Any suggested circle that uses it will be withdrawn.")) {
      act(() => api("DELETE", `/api/people/${state.pid}/listings/${b.dataset.close}`), "Removed.");
    }
  }));
}

// -------------------------------------------------------------- community

function renderCommunity() {
  const q = (recall("q") || "").toLowerCase();
  const items = state.community.filter((l) => !q || `${l.text} ${l.owner} ${l.concepts.join(" ")}`.toLowerCase().includes(q));
  view.innerHTML = `
    <section class="lede"><h1>Maple Commons</h1>
      <p>Everything neighbours are offering and looking for. You don't have to find matches yourself; circles find you.</p></section>
    <input class="search" id="q" type="search" placeholder="Search offers and needs" value="${esc(q)}" aria-label="Search">
    <section class="grid">${items.map((l) => `<div class="card listing">
        <span class="kind ${l.kind}">${l.kind === "offer" ? "Offers" : "Needs"}</span>
        <p class="text">${esc(l.text)}</p>
        <div class="row between"><span class="meta">${esc(l.owner)} · ${esc(l.zone)} · ${esc(MODE[l.mode])}</span>
          <button class="link" data-block="${esc(l.owner_id)}" data-name="${esc(l.owner)}">Don't match me</button></div>
      </div>`).join("") || `<div class="empty">No listings match.</div>`}</section>`;
  const input = document.getElementById("q");
  input.addEventListener("input", () => { remember("q", input.value); renderCommunity(); document.getElementById("q").focus(); });
  view.querySelectorAll("[data-block]").forEach((b) => b.addEventListener("click", () => {
    if (confirm(`Never match you with ${b.dataset.name}? They won't be told, and neither of you will see the other.`)) {
      act(() => api("POST", `/api/people/${state.pid}/blocks`, { other_id: b.dataset.block }), "Done. They won't be told.");
    }
  }));
}

// ---------------------------------------------------------------- profile

function renderProfile() {
  const me = state.dash.me, s = state.status;
  const zoneOpts = (sel) => s.zones.map((z) => `<option ${z === sel ? "selected" : ""}>${z}</option>`).join("");
  const travelOpts = (sel) => [0, 1, 2, 3].map((t) => `<option value="${t}" ${t === sel ? "selected" : ""}>${t === 0 ? "my zone only" : `${t} zone${t > 1 ? "s" : ""} away`}</option>`).join("");
  const slots = (sel) => s.slots.map((x) => `<label><input type="checkbox" name="slot" value="${x}" ${sel.includes(x) ? "checked" : ""}> ${slot(x)}</label>`).join("");
  view.innerHTML = `
    <section class="lede"><h1>${esc(me.name)}</h1><p>Only your zone is used for matching, never an address.</p></section>
    <form class="card add" id="profile">
      <div class="row">
        <label class="field"><span>Zone</span><select name="zone">${zoneOpts(me.zone)}</select></label>
        <label class="field"><span>I can travel</span><select name="travel">${travelOpts(me.max_travel)}</select></label>
      </div>
      <div class="field"><span>Usually free</span><div class="checks">${slots(me.availability)}</div></div>
      <div><button class="primary" type="submit">Save</button></div>
    </form>
    <section class="section"><h2>People you won't be matched with</h2>
      ${state.dash.blocked.length ? `<p>${state.dash.blocked.map((b) => esc(b.name)).join(", ")}</p>` : `<p class="fineprint">No one. Use "Don't match me" in Community.</p>`}</section>
    <section class="section"><h2>Add a new neighbour</h2>
      <form class="card add" id="join">
        <div class="row">
          <label class="field"><span>Name</span><input type="text" name="name" required maxlength="60"></label>
          <label class="field"><span>Zone</span><select name="zone">${zoneOpts("central")}</select></label>
          <label class="field"><span>Can travel</span><select name="travel">${travelOpts(1)}</select></label>
        </div>
        <div class="field"><span>Usually free</span><div class="checks">${slots(["weekend"])}</div></div>
        <div><button class="secondary" type="submit">Join Maple Commons</button></div>
      </form></section>`;

  const read = (form) => {
    const f = new FormData(form);
    return { zone: f.get("zone"), max_travel: Number(f.get("travel")), availability: f.getAll("slot") };
  };
  document.getElementById("profile").addEventListener("submit", (e) => {
    e.preventDefault();
    act(() => api("PUT", `/api/people/${state.pid}`, read(e.target)), "Saved. Looking for circles…");
  });
  document.getElementById("join").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const { id } = await api("POST", "/api/people", { name: new FormData(e.target).get("name"), ...read(e.target) });
      await loadPeople(); switchTo(id); setTab("listings"); toast("Welcome. Add what you can offer and what you need.");
    } catch (err) { toast(err.message); }
  });
}

// ------------------------------------------------------------------ shell

function render() {
  ({ circles: renderCircles, listings: renderListings, community: renderCommunity, profile: renderProfile })[state.tab]();
}

function setTab(tab) {
  state.tab = tab; remember("tab", tab);
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
  if (state.dash) render();
}

function switchTo(pid) {
  state.pid = pid; remember("pid", pid);
  document.getElementById("persona").value = pid;
  refresh();
}

document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
document.getElementById("persona").addEventListener("change", (e) => switchTo(e.target.value));
document.getElementById("run").addEventListener("click", () => act(async () => {
  const { new_circles } = await api("POST", "/api/match");
  toast(new_circles ? `Found ${new_circles} new circle${new_circles > 1 ? "s" : ""}.` : "No new circles right now.");
}));
document.getElementById("reset").addEventListener("click", () => {
  if (confirm("Reset the demo to its starting data?")) act(async () => { await api("POST", "/api/reset"); await loadPeople(); }, "Demo reset.");
});

(async () => {
  const tab = recall("tab");
  if (["circles", "listings", "community", "profile"].includes(tab)) setTab(tab);
  await loadPeople();
  await refresh();
})();
