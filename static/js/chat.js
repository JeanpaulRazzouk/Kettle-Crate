const session = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);

const railEl = document.getElementById("rail");
const stageEl = document.getElementById("stage");
const promptEl = document.getElementById("stage-prompt");
const quickEl = document.getElementById("stage-quick");
const trailEl = document.getElementById("trail");
const formWrapEl = document.getElementById("form-wrap");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

// Keys match the `current_field` enum the backend's tool schema reports
// directly (see llm.py) — the frontend trusts this instead of guessing it
// from the reply's wording.
const FIELDS = [
  { key: "issue", label: "Issue", icon: "❗" },
  { key: "name", label: "Name", icon: "👤" },
  { key: "email", label: "Email", icon: "✉️" },
  { key: "order_number", label: "Order", icon: "🧾" },
  { key: "item", label: "Item", icon: "📦" },
  { key: "resolution", label: "Fix", icon: "🔧" },
  { key: "phone", label: "Phone", icon: "📞" },
];

const RESOLUTION_QUICK_REPLIES = ["Refund", "Replacement", "Something else"];

let currentIndex = 0; // index into FIELDS — how far the rail has progressed
let previousIndex = 0; // currentIndex as of the last render, to spot new completions
let filed = false;

function renderRichText(el, text) {
  el.textContent = "";
  const parts = text.split(/\*\*(.+?)\*\*/g);
  parts.forEach((part, i) => {
    if (!part) return;
    if (i % 2 === 1) {
      const strong = document.createElement("strong");
      strong.textContent = part;
      el.appendChild(strong);
    } else {
      el.appendChild(document.createTextNode(part));
    }
  });
}

function renderRail() {
  // Only a step that just flipped to done (not one already done last render)
  // gets the completion pop + mini confetti — the final "filed" moment has
  // its own big celebration already, so it's excluded here.
  const justCompletedIndex = !filed && currentIndex > previousIndex ? currentIndex - 1 : -1;

  railEl.innerHTML = "";
  FIELDS.forEach((f, i) => {
    const done = filed || i < currentIndex;
    const step = document.createElement("div");
    step.className = "rail__step";
    if (done) step.classList.add("is-done");
    else if (i === currentIndex) step.classList.add("is-active");
    if (i === justCompletedIndex) step.classList.add("just-done");

    const dot = document.createElement("div");
    dot.className = "rail__dot";
    dot.textContent = done ? "✓" : f.icon;

    const label = document.createElement("div");
    label.className = "rail__label";
    label.textContent = f.label;

    step.appendChild(dot);
    step.appendChild(label);
    railEl.appendChild(step);
  });

  previousIndex = currentIndex;

  if (justCompletedIndex >= 0) {
    requestAnimationFrame(() => {
      const dot = railEl.querySelector(".rail__step.just-done .rail__dot");
      if (dot) {
        const r = dot.getBoundingClientRect();
        confettiBurst(r.left + r.width / 2, r.top + r.height / 2, 12);
      }
    });
  }
}

function showInput() {
  formWrapEl.classList.add("is-open");
  setTimeout(() => input.focus(), 300);
}

function hideInput() {
  formWrapEl.classList.remove("is-open");
}

function addTrailChip(fieldKey, value) {
  const def = FIELDS.find((f) => f.key === fieldKey) || { label: "Note" };
  const chip = document.createElement("div");
  chip.className = "trail__chip";
  const b = document.createElement("b");
  b.textContent = def.label + ": ";
  chip.appendChild(b);
  chip.appendChild(document.createTextNode(value));
  trailEl.appendChild(chip);
}

function setPrompt(text) {
  promptEl.style.animation = "none";
  void promptEl.offsetHeight; // force reflow so the entrance animation replays
  promptEl.style.animation = "";
  renderRichText(promptEl, text);
}

function showTyping() {
  promptEl.innerHTML = '<span class="stage__typing"><span></span><span></span><span></span></span>';
}

function renderQuickReplies(currentField) {
  quickEl.innerHTML = "";

  if (currentField === "resolution") {
    RESOLUTION_QUICK_REPLIES.forEach((label) => {
      const btn = document.createElement("button");
      btn.className = "quick-pill";
      btn.textContent = label;
      btn.onclick = () => sendMessage(label);
      quickEl.appendChild(btn);
    });

    const reveal = document.createElement("button");
    reveal.type = "button";
    reveal.className = "reveal-link";
    reveal.textContent = "or type your own answer";
    reveal.onclick = () => showInput();
    quickEl.appendChild(reveal);

    hideInput();
  } else {
    showInput();
  }
}

function showSuccess() {
  stageEl.classList.add("stage--success");
  quickEl.innerHTML = "";
  formWrapEl.style.display = "none";
  const rect = stageEl.getBoundingClientRect();
  confettiBurst(rect.left + rect.width / 2, rect.top + 20, 70);
}

async function sendMessage(text) {
  if (!text.trim() || filed) return;

  addTrailChip(FIELDS[currentIndex].key, text.trim());
  input.value = "";
  sendBtn.classList.remove("is-ready");
  quickEl.innerHTML = "";
  sendBtn.disabled = true;
  showTyping();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, message: text.trim() }),
    });
    const data = await res.json();

    if (!res.ok) {
      setPrompt(data.error || "Sorry, the support bot is unavailable right now.");
      renderQuickReplies(null);
      return;
    }

    if (data.filed) {
      filed = true;
      currentIndex = FIELDS.length - 1;
      setPrompt(data.reply);
      renderRail();
      showSuccess();
      return;
    }

    const idx = FIELDS.findIndex((f) => f.key === data.current_field);
    if (idx >= 0) currentIndex = Math.max(currentIndex, idx);
    renderRail();
    setPrompt(data.reply);
    renderQuickReplies(data.current_field);
  } catch (err) {
    setPrompt("Sorry, the support bot is unavailable right now.");
  } finally {
    sendBtn.disabled = false;
    if (formWrapEl.classList.contains("is-open")) input.focus();
  }
}

form.onsubmit = (e) => {
  e.preventDefault();
  sendMessage(input.value);
};

input.addEventListener("input", () => {
  sendBtn.classList.toggle("is-ready", input.value.trim().length > 0);
});

quickEl.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-send], [data-focus]");
  if (!btn) return;
  if (btn.dataset.focus) {
    showInput();
    return;
  }
  if (btn.dataset.send) sendMessage(btn.dataset.send);
});

renderRail();
