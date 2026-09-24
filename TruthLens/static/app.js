// TruthLens front end. All user text is inserted with textContent (never innerHTML).
const $ = (s) => document.querySelector(s);
const STATUSES = window.TL.statuses;
const RISK_CLASS = { "High Risk": "risk-high", "Risk Flag": "risk-flag", "Low Risk": "risk-low" };
const CARD_CLASS = { "High Risk": "r-high", "Risk Flag": "r-flag", "Low Risk": "r-low" };
const STATUS_CLASS = { "Unverified": "st-unverified", "Verified True": "st-true", "False": "st-false", "Misleading": "st-misleading" };

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
const fmtTime = (iso) => new Date(iso).toLocaleString();

async function api(url, opts) {
  let res;
  try { res = await fetch(url, opts); } catch { throw new Error("Cannot reach the server."); }
  let data = null;
  try { data = await res.json(); } catch { /* ignore */ }
  if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status}).`);
  return data;
}
const jsonOpts = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const riskBadge = (c) => el("span", "badge " + RISK_CLASS[c.risk_level], c.risk_level);
const statusBadge = (c) => el("span", "badge " + STATUS_CLASS[c.status], c.status);
function flagChips(c) {
  const box = el("div", "badges");
  if (!c.flags.length) box.append(el("span", "chip", "No flags"));
  c.flags.forEach((f) => box.append(el("span", "chip", f)));
  return box;
}

/* ---------- feed ---------- */
async function loadFeed() {
  const feed = $("#feed");
  const cat = $("#filter-category").value, st = $("#filter-status").value;
  const params = new URLSearchParams();
  if (cat !== "All") params.set("category", cat);
  if (st !== "All") params.set("status", st);
  feed.replaceChildren(el("p", "state", "Loading claims…"));
  try {
    const claims = await api("/api/claims?" + params.toString());
    if (!claims.length) {
      const filtered = cat !== "All" || st !== "All";
      feed.replaceChildren(el("p", "state", filtered ? "No claims match these filters." : "No claims submitted yet."));
      return;
    }
    feed.replaceChildren(...claims.map(renderCard));
  } catch (e) {
    feed.replaceChildren(el("p", "state error", "Could not load claims: " + e.message));
  }
}

function renderCard(c) {
  const card = el("article", "card " + CARD_CLASS[c.risk_level]);
  const badges = el("div", "badges");
  badges.append(el("span", "lbl", "Risk"), riskBadge(c), el("span", "lbl", "Truth status"), statusBadge(c));
  card.append(badges);
  card.append(el("div", "meta", `${c.category} · ${c.platform}`));
  card.append(el("p", "claim-text", c.text));
  card.append(flagChips(c));
  const foot = el("div", "card-foot");
  foot.style.marginTop = "10px";
  foot.append(el("span", "muted", "Submitted " + fmtTime(c.created_at)));
  const btn = el("button", "btn small", "View Details");
  btn.type = "button";
  btn.addEventListener("click", () => openDetail(c.id));
  foot.append(btn);
  card.append(foot);
  return card;
}

/* ---------- submit ---------- */
$("#claim-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#form-msg");
  const text = $("#text").value.trim();
  if (!text) { msg.className = "err"; msg.textContent = "Please enter the claim text."; return; }
  const btn = $("#claim-form button[type=submit]");
  btn.disabled = true;
  try {
    await api("/api/claims", jsonOpts("POST", {
      text, platform: $("#platform").value, category: $("#category").value, source_link: $("#source_link").value.trim(),
    }));
    msg.className = "ok"; msg.textContent = "Claim submitted successfully.";
    $("#claim-form").reset();
    loadFeed();
  } catch (err) {
    msg.className = "err"; msg.textContent = err.message;
  } finally { btn.disabled = false; }
});

/* ---------- detail modal ---------- */
function row(dl, label, node) {
  dl.append(el("dt", "", label));
  const dd = el("dd");
  dd.append(node);
  dl.append(dd);
}

async function openDetail(id) {
  const modal = $("#modal"), box = $("#detail");
  modal.classList.remove("hidden");
  box.replaceChildren(el("p", "state", "Loading…"));
  try { renderDetail(await api("/api/claims/" + id)); }
  catch (e) { box.replaceChildren(el("p", "state error", "Could not load claim: " + e.message)); }
}

function renderDetail(c, okMessage) {
  const box = $("#detail");
  const box2 = el("div");
  const dl0 = el("dl", "dl");
  row(dl0, "Claim", el("div", "full-text", c.text));
  row(dl0, "Platform", document.createTextNode(c.platform));
  row(dl0, "Category", document.createTextNode(c.category));
  let link;
  if (!c.source_link) link = document.createTextNode("None provided");
  else if (/^https?:\/\//i.test(c.source_link)) {
    link = el("a", "", c.source_link); link.href = c.source_link; link.target = "_blank"; link.rel = "noopener noreferrer";
  } else link = document.createTextNode(c.source_link);
  row(dl0, "Source Link", link);
  row(dl0, "Submitted At", document.createTextNode(fmtTime(c.created_at)));

  const riskSec = el("section", "sec sec-risk");
  riskSec.append(el("h3", "", "RISK ASSESSMENT"));
  const dl1 = el("dl", "dl");
  row(dl1, "Risk Level", riskBadge(c));
  row(dl1, "Risk Flags", flagChips(c));
  riskSec.append(dl1, el("p", "muted note", "Risk level indicates signals that may deserve closer review. It does not determine whether a claim is true or false. High Risk does not mean False."));

  const truthSec = el("section", "sec sec-truth");
  truthSec.append(el("h3", "", "TRUTH REVIEW"));
  const dl2 = el("dl", "dl");
  row(dl2, "Status", statusBadge(c));
  const note = c.reviewer_note || (c.status === "Unverified" ? "Not reviewed yet." : "No note provided.");
  row(dl2, "Reviewer Note", document.createTextNode(note));
  truthSec.append(dl2);
  const dl = box2;
  const claimSec = el("section", "sec");
  claimSec.append(el("h3", "", "CLAIM DETAILS"), dl0);
  box2.append(claimSec, riskSec, truthSec);

  const review = el("form", "review");
  review.append(el("h3", "", "REVIEWER CONTROLS"), el("p", "muted note", "Set the truth status after checking evidence. This is separate from the automatic risk level."));
  const l1 = el("label", "", "Status"); l1.htmlFor = "r-status";
  const sel = el("select"); sel.id = "r-status";
  STATUSES.forEach((s) => { const o = el("option", "", s); o.selected = s === c.status; sel.append(o); });
  const l2 = el("label", "", "Reviewer Note"); l2.htmlFor = "r-note";
  const ta = el("textarea"); ta.id = "r-note"; ta.rows = 3; ta.maxLength = 500; ta.value = c.reviewer_note;
  ta.placeholder = "Short evidence-based note (max 500 characters)";
  const actions = el("div", "actions");
  const btn = el("button", "btn primary", "Update Review"); btn.type = "submit";
  const msg = el("span", okMessage ? "ok" : "", okMessage || ""); msg.setAttribute("role", "status");
  actions.append(btn, msg);
  review.append(l1, sel, l2, ta, actions);
  review.append(el("p", "muted note", "The claim text, platform, category, link and risk flags cannot be edited after submission. Submit a new claim for a corrected version."));

  review.addEventListener("submit", async (e) => {
    e.preventDefault();
    btn.disabled = true;
    try {
      const updated = await api(`/api/claims/${c.id}/review`, jsonOpts("PATCH", { status: sel.value, reviewer_note: ta.value }));
      renderDetail(updated, "Review updated.");
      loadFeed();
    } catch (err) { msg.className = "err"; msg.textContent = err.message; btn.disabled = false; }
  });
  box.replaceChildren(box2, review);
}

const closeModal = () => $("#modal").classList.add("hidden");
$("#modal-close").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

/* ---------- filters + demo tools ---------- */
$("#filter-category").addEventListener("change", loadFeed);
$("#filter-status").addEventListener("change", loadFeed);
$("#demo-load").addEventListener("click", async () => {
  try { await api("/api/demo/load", { method: "POST" }); } catch (e) { alert(e.message); }
  loadFeed();
});
$("#demo-clear").addEventListener("click", async () => {
  if (!confirm("Delete ALL claims? This cannot be undone.")) return;
  try { await api("/api/demo/reset", { method: "POST" }); } catch (e) { alert(e.message); }
  loadFeed();
});

loadFeed();
