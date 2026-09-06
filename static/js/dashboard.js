const cardsEl = document.getElementById("cards");
const searchEl = document.getElementById("search");
const pillsEl = document.querySelectorAll(".pill");
const statTotal = document.getElementById("stat-total");
const statNew = document.getElementById("stat-new");
const statContacted = document.getElementById("stat-contacted");
const statResolved = document.getElementById("stat-resolved");

let allComplaints = [];
let activeFilter = "all";
const expandedIds = new Set();
const logCache = {};
const draftCache = {};

const STATUS_LABEL = { new: "New", contacted: "Contacted", resolved: "Resolved" };

function initials(name) {
  if (!name) return "?";
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

function field(label, value) {
  const div = document.createElement("div");
  const b = document.createElement("b");
  b.textContent = label;
  div.appendChild(b);
  div.appendChild(document.createTextNode(value || "—"));
  return div;
}

function actionButton(text, cls, onClick) {
  const btn = document.createElement("button");
  btn.className = "btn " + cls;
  btn.textContent = text;
  btn.onclick = onClick;
  return btn;
}

function buildCard(c) {
  const card = document.createElement("div");
  card.className = "card";

  const top = document.createElement("div");
  top.className = "card__top";

  const who = document.createElement("div");
  who.className = "card__who";
  const avatar = document.createElement("div");
  avatar.className = "card__avatar";
  avatar.textContent = initials(c.name);
  const nameWrap = document.createElement("div");
  const name = document.createElement("div");
  name.className = "card__name";
  name.textContent = c.name || "Unknown customer";
  const meta = document.createElement("div");
  meta.className = "card__meta";
  meta.textContent = (c.email || "no email on file") + (c.is_repeat ? " · repeat customer" : "");
  nameWrap.appendChild(name);
  nameWrap.appendChild(meta);
  who.appendChild(avatar);
  who.appendChild(nameWrap);

  const right = document.createElement("div");
  right.className = "card__right";
  const date = document.createElement("div");
  date.className = "card__date";
  date.textContent = c.date || "";
  right.appendChild(date);

  if (c.urgency === "high") {
    const urgent = document.createElement("span");
    urgent.className = "badge badge--urgent";
    urgent.textContent = "🔥 Urgent";
    right.appendChild(urgent);
  }

  const badge = document.createElement("span");
  badge.className = "badge badge--" + c.status;
  badge.innerHTML = '<span class="badge__dot"></span>';
  badge.appendChild(document.createTextNode(STATUS_LABEL[c.status] || c.status));
  right.appendChild(badge);

  top.appendChild(who);
  top.appendChild(right);

  const grid = document.createElement("div");
  grid.className = "card__grid";
  grid.appendChild(field("Order", c.order_no));
  grid.appendChild(field("Item", c.item));
  grid.appendChild(field("Wants", c.resolution));
  grid.appendChild(field("Phone", c.phone));

  const issue = document.createElement("div");
  issue.className = "card__issue";
  const issueLabel = document.createElement("b");
  issueLabel.textContent = "What went wrong";
  issue.appendChild(issueLabel);
  issue.appendChild(document.createTextNode(c.issue || "No details given."));

  const actions = document.createElement("div");
  actions.className = "card__actions";

  if (c.email) {
    const mail = document.createElement("a");
    mail.className = "link-chip";
    mail.href = "mailto:" + encodeURIComponent(c.email);
    mail.textContent = "✉ Email";
    actions.appendChild(mail);
  }
  if (c.phone) {
    const tel = document.createElement("a");
    tel.className = "link-chip";
    tel.href = "tel:" + c.phone.replace(/[^\d+]/g, "");
    tel.textContent = "☎ Call";
    actions.appendChild(tel);
  }

  if (c.status === "new") {
    actions.appendChild(actionButton("Mark contacted", "btn--contact", () => setStatus(c.id, "contacted")));
  }
  if (c.status !== "resolved") {
    actions.appendChild(
      actionButton("Mark resolved", "btn--resolve", (e) => {
        confettiBurst(e.clientX, e.clientY, 36);
        setStatus(c.id, "resolved");
      })
    );
  }
  if (c.status !== "new") {
    actions.appendChild(actionButton("Reopen", "btn--reopen", () => setStatus(c.id, "new")));
  }

  const isOpen = expandedIds.has(c.id);
  const transcriptToggle = document.createElement("button");
  transcriptToggle.type = "button";
  transcriptToggle.className = "transcript-toggle";
  transcriptToggle.textContent = isOpen ? "Hide conversation" : "💬 View conversation";

  const transcriptWrap = document.createElement("div");
  transcriptWrap.className = "card__transcript" + (isOpen ? " is-open" : "");

  transcriptToggle.onclick = () => toggleTranscript(c.id, transcriptWrap, transcriptToggle);

  const draftToggle = document.createElement("button");
  draftToggle.type = "button";
  draftToggle.className = "transcript-toggle";
  draftToggle.textContent = "✍️ Draft a reply";

  const draftWrap = document.createElement("div");
  draftWrap.className = "card__transcript";

  draftToggle.onclick = () => toggleDraft(c.id, draftWrap, draftToggle);

  card.appendChild(top);
  card.appendChild(grid);
  card.appendChild(issue);
  card.appendChild(actions);
  card.appendChild(transcriptToggle);
  card.appendChild(transcriptWrap);
  card.appendChild(draftToggle);
  card.appendChild(draftWrap);

  if (isOpen) loadTranscript(c.id, transcriptWrap);

  return card;
}

function paintDraft(wrapEl, text) {
  wrapEl.innerHTML = "";
  const box = document.createElement("div");
  box.className = "draft-box";

  const textarea = document.createElement("textarea");
  textarea.className = "draft-box__text";
  textarea.value = text;

  const copyBtn = document.createElement("button");
  copyBtn.type = "button";
  copyBtn.className = "btn btn--ghost";
  copyBtn.textContent = "Copy";
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(textarea.value).then(() => {
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy"), 1500);
    });
  };

  box.appendChild(textarea);
  box.appendChild(copyBtn);
  wrapEl.appendChild(box);
}

async function toggleDraft(id, wrapEl, btnEl) {
  if (wrapEl.classList.contains("is-open")) {
    wrapEl.classList.remove("is-open");
    btnEl.textContent = "✍️ Draft a reply";
    return;
  }
  wrapEl.classList.add("is-open");
  btnEl.textContent = "Hide draft";

  if (draftCache[id]) {
    paintDraft(wrapEl, draftCache[id]);
    return;
  }

  wrapEl.innerHTML = '<div class="transcript__loading">Writing a draft…</div>';
  try {
    const res = await fetch(`/api/complaints/${encodeURIComponent(id)}/draft-reply`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      wrapEl.innerHTML = "";
      const empty = document.createElement("div");
      empty.className = "transcript__empty";
      empty.textContent = data.error || "Could not generate a draft right now.";
      wrapEl.appendChild(empty);
      return;
    }
    draftCache[id] = data.draft;
    paintDraft(wrapEl, data.draft);
  } catch (err) {
    wrapEl.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "transcript__empty";
    empty.textContent = "Could not generate a draft right now.";
    wrapEl.appendChild(empty);
  }
}

function paintTranscript(wrapEl, entries) {
  wrapEl.innerHTML = "";
  if (!entries || entries.length === 0) {
    const empty = document.createElement("div");
    empty.className = "transcript__empty";
    empty.textContent = "No messages recorded.";
    wrapEl.appendChild(empty);
    return;
  }

  const box = document.createElement("div");
  box.className = "transcript";
  entries.forEach((e) => {
    const row = document.createElement("div");
    row.className = "transcript__row transcript__row--" + (e.who === "USER" ? "user" : "bot");

    const who = document.createElement("div");
    who.className = "transcript__who";
    who.textContent = e.who === "USER" ? "Customer" : "Kettle";

    const text = document.createElement("div");
    text.className = "transcript__text";
    text.textContent = e.text;

    row.appendChild(who);
    row.appendChild(text);
    box.appendChild(row);
  });
  wrapEl.appendChild(box);
}

async function loadTranscript(id, wrapEl) {
  if (logCache[id]) {
    paintTranscript(wrapEl, logCache[id]);
    return;
  }

  wrapEl.innerHTML = '<div class="transcript__loading">Loading conversation…</div>';
  try {
    const res = await fetch(`/api/complaints/${encodeURIComponent(id)}/log`);
    const data = await res.json();
    if (!res.ok) {
      wrapEl.innerHTML = "";
      const empty = document.createElement("div");
      empty.className = "transcript__empty";
      empty.textContent = data.error || "No conversation log found for this complaint.";
      wrapEl.appendChild(empty);
      return;
    }
    logCache[id] = data.log;
    paintTranscript(wrapEl, data.log);
  } catch (err) {
    wrapEl.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "transcript__empty";
    empty.textContent = "Couldn't load the conversation.";
    wrapEl.appendChild(empty);
  }
}

function toggleTranscript(id, wrapEl, btnEl) {
  if (wrapEl.classList.contains("is-open")) {
    wrapEl.classList.remove("is-open");
    expandedIds.delete(id);
    btnEl.textContent = "💬 View conversation";
    return;
  }
  wrapEl.classList.add("is-open");
  expandedIds.add(id);
  btnEl.textContent = "Hide conversation";
  loadTranscript(id, wrapEl);
}

function render() {
  const q = searchEl.value.trim().toLowerCase();
  const filtered = allComplaints.filter((c) => {
    if (activeFilter !== "all" && c.status !== activeFilter) return false;
    if (!q) return true;
    const haystack = [c.name, c.email, c.order_no, c.item, c.issue].join(" ").toLowerCase();
    return haystack.includes(q);
  });

  cardsEl.innerHTML = "";
  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.innerHTML = '<div class="big">🫖</div>';
    empty.appendChild(document.createTextNode("No complaints match here."));
    cardsEl.appendChild(empty);
    return;
  }
  filtered.forEach((c, i) => {
    const card = buildCard(c);
    card.style.animationDelay = Math.min(i * 0.05, 0.4) + "s";
    cardsEl.appendChild(card);
  });
}

function renderStats(stats) {
  animateCount(statTotal, stats.total);
  animateCount(statNew, stats.new);
  animateCount(statContacted, stats.contacted);
  animateCount(statResolved, stats.resolved);
}

async function load() {
  const res = await fetch("/api/complaints");
  if (res.status === 401 || res.redirected) {
    window.location.href = "/login";
    return;
  }
  const data = await res.json();
  allComplaints = data.complaints;
  renderStats(data.stats);
  render();
}

async function setStatus(id, status) {
  await fetch(`/api/complaints/${encodeURIComponent(id)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  load();
}

searchEl.addEventListener("input", render);
pillsEl.forEach((pill) => {
  pill.addEventListener("click", () => {
    pillsEl.forEach((p) => p.classList.remove("active"));
    pill.classList.add("active");
    activeFilter = pill.dataset.status;
    render();
  });
});

load();
setInterval(load, 30000);
