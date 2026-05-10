/* chat.js — MindHeist Session */

"use strict";

/* ============================================================
   MOOD ENGINE
   Reads #mood-config JSON, applies CSS variables on <html>.
   Backend API:
     window.MindHeist.setMood("tense")
     window.MindHeist.setMood({ accent: "#7c5cff", glow: "…" })
     postMessage({ type: "mindheist:mood", mood: "tense" })
============================================================ */
const MOOD_CONFIG = JSON.parse(
  document.getElementById("mood-config").textContent
);
const VAR_MAP = {
  bg:             "--bg",
  surface:        "--surface",
  surface2:       "--surface-2",
  ink:            "--ink",
  inkDim:         "--ink-dim",
  inkMute:        "--ink-mute",
  line:           "--line",
  accent:         "--accent",
  accent2:        "--accent-2",
  glow:           "--glow",
  ambient:        "--ambient",
  userBubble:     "--user-bubble",
  userInk:        "--user-ink",
  teacherBubble:  "--teacher-bubble",
  teacherInk:     "--teacher-ink",
  teacherAccent:  "--teacher-accent",
};

function applyMoodVars(obj) {
  const root = document.documentElement;
  Object.entries(obj).forEach(([k, v]) => {
    const cssVar = VAR_MAP[k];
    if (cssVar && v != null) root.style.setProperty(cssVar, v);
  });
}

function setMood(arg) {
  let label;
  if (typeof arg === "string") {
    const mood = MOOD_CONFIG.moods[arg];
    if (!mood) { console.warn("[MindHeist] unknown mood:", arg); return; }
    document.documentElement.setAttribute("data-mood", arg);
    applyMoodVars(mood);
    label = mood.label || arg;
  } else if (arg && typeof arg === "object") {
    const activeName = document.documentElement.getAttribute("data-mood");
    const base = MOOD_CONFIG.moods[activeName] || {};
    applyMoodVars(Object.assign({}, base, arg));
    label = arg.label || (base.label ? base.label + " ✶" : "Custom");
  }
  const lbl = document.getElementById("mood-label");
  if (lbl && label) lbl.textContent = label;
}

window.addEventListener("message", (e) => {
  if (e.data && e.data.type === "mindheist:mood") setMood(e.data.mood);
});

window.MindHeist = {
  setMood,
  getMoods: () => Object.keys(MOOD_CONFIG.moods),
  getConfig: () => MOOD_CONFIG,
};

setMood(MOOD_CONFIG.active || "neutral");

/* ============================================================
   SESSION LOAD
   Blueprint is stored in sessionStorage by the main menu
   after a successful /api/work call.
============================================================ */
const _raw = sessionStorage.getItem("mindheist_blueprint");
if (!_raw) {
  window.location.href = "/";
  throw new Error("No session blueprint — redirecting to home");
}
const blueprint = JSON.parse(_raw);

/* ============================================================
   UI POPULATION
   Fill teacher card, scenes list, and textarea placeholder
   from the blueprint.
============================================================ */
const ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X"];

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function populateUI() {
  const t = blueprint.teacher;
  const s = blueprint.session;

  document.title = "MindHeist — " + t.name;

  document.getElementById("teacher-name").textContent = t.name;
  document.getElementById("teacher-role").textContent =
    t.role + " · " + s.language + " · turn 1 of " + s.estimated_turns;

  const scenesList = document.getElementById("scenes-list");
  blueprint.phases.forEach((phase, i) => {
    const el = document.createElement("div");
    el.className = "scene" + (i === 0 ? " active" : "");
    el.dataset.phaseId = phase.id;
    el.innerHTML =
      `<div class="pico">${escapeHtml(ROMAN[i] || String(i + 1))}</div>` +
      `<div class="text">` +
        `<div class="title">${escapeHtml(phase.name)}</div>` +
        `<div class="sub">${escapeHtml(phase.goal)}</div>` +
      `</div>` +
      `<div class="num">${String(i + 1).padStart(2, "0")}</div>`;
    scenesList.appendChild(el);
  });

  document.getElementById("composer-input").placeholder =
    "Respond to " + t.name + "…";
}

populateUI();

/* ============================================================
   CHAT ENGINE
============================================================ */
const feedEl       = document.getElementById("feed");
const transcriptEl = document.getElementById("transcript");
const inputEl      = document.getElementById("composer-input");
const sendBtnEl    = document.getElementById("send-btn");

const history = [];
let currentPhaseIndex = 0;
let currentTurn = 1;

function nowHHMM() {
  const d = new Date();
  return String(d.getHours()).padStart(2, "0") + ":" +
         String(d.getMinutes()).padStart(2, "0");
}

function scrollBottom() {
  requestAnimationFrame(() =>
    transcriptEl.scrollTo({ top: transcriptEl.scrollHeight, behavior: "smooth" })
  );
}

function addDayMarker(text) {
  const el = document.createElement("div");
  el.className = "day";
  el.textContent = text;
  feedEl.appendChild(el);
}

const TEACHER_ICON =
  `<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true">` +
  `<circle cx="50" cy="38" r="18"/>` +
  `<path d="M16 100c0-20 15-36 34-36s34 16 34 36z"/>` +
  `</svg>`;

function addTeacherMessage(text) {
  const el = document.createElement("div");
  el.className = "msg teacher";
  el.innerHTML =
    `<div class="av">${TEACHER_ICON}</div>` +
    `<div class="body">` +
      `<div class="meta">` +
        `<span class="name">${escapeHtml(blueprint.teacher.name)}</span>` +
        `<span class="time">${nowHHMM()}</span>` +
      `</div>` +
      `<div class="bubble"></div>` +
    `</div>`;
  el.querySelector(".bubble").textContent = text;
  feedEl.appendChild(el);
  scrollBottom();
  return el;
}

function addUserMessage(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML =
    `<div class="body">` +
      `<div class="meta">` +
        `<span class="time">${nowHHMM()}</span>` +
        `<span class="name">You</span>` +
      `</div>` +
      `<div class="bubble"></div>` +
    `</div>` +
    `<div class="av">?</div>`;
  el.querySelector(".bubble").textContent = text;
  feedEl.appendChild(el);
  scrollBottom();
}

function showTyping() {
  const el = document.createElement("div");
  el.className = "msg teacher";
  el.id = "typing-indicator";
  el.innerHTML =
    `<div class="av">${TEACHER_ICON}</div>` +
    `<div class="body">` +
      `<div class="meta">` +
        `<span class="name">${escapeHtml(blueprint.teacher.name)}</span>` +
        `<span class="time">${nowHHMM()}</span>` +
      `</div>` +
      `<div class="typing"><span></span><span></span><span></span></div>` +
    `</div>`;
  feedEl.appendChild(el);
  scrollBottom();
}

function removeTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function updateActiveScene(index) {
  document.querySelectorAll(".scene").forEach((el, i) =>
    el.classList.toggle("active", i === index)
  );
}

function updateTurnCounter(turn) {
  const roleEl = document.getElementById("teacher-role");
  if (!roleEl) return;
  roleEl.textContent =
    blueprint.teacher.role + " · " + blueprint.session.language +
    " · turn " + turn + " of " + blueprint.session.estimated_turns;
}

/* ---- textarea autosize ---- */
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
});

/* ---- send on Enter ---- */
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
sendBtnEl.addEventListener("click", sendMessage);

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || sendBtnEl.disabled) return;

  addUserMessage(text);
  const historySnapshot = history.slice();
  history.push({ role: "user", content: text });

  inputEl.value = "";
  inputEl.style.height = "auto";
  sendBtnEl.disabled = true;

  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: blueprint.session_id,
        message: text,
        history: historySnapshot,
      }),
    });

    removeTyping();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      addTeacherMessage("[Error: " + (err.detail || res.statusText) + "]");
      return;
    }

    const data = await res.json();
    addTeacherMessage(data.reply);
    history.push({ role: "teacher", content: data.reply });

    currentTurn++;
    updateTurnCounter(currentTurn);

    if (data.mood) setMood(data.mood);

    if (typeof data.phase_index === "number" && data.phase_index !== currentPhaseIndex) {
      currentPhaseIndex = data.phase_index;
      updateActiveScene(currentPhaseIndex);
      const phase = blueprint.phases[currentPhaseIndex];
      if (phase) {
        addDayMarker(
          "Scene " + (ROMAN[currentPhaseIndex] || currentPhaseIndex + 1) +
          " · " + phase.name
        );
      }
    }

  } catch (err) {
    removeTyping();
    addTeacherMessage("[Connection error: " + err.message + "]");
  } finally {
    sendBtnEl.disabled = false;
    inputEl.focus();
  }
}

/* ---- hint button — request a hint from the teacher ---- */
document.getElementById("hint-btn").addEventListener("click", async () => {
  if (sendBtnEl.disabled) return;

  sendBtnEl.disabled = true;
  showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: blueprint.session_id,
        message: "[SYSTEM: The student requested a hint. Give a gentle nudge without revealing the full answer.]",
        history: history.slice(),
      }),
    });

    removeTyping();

    if (res.ok) {
      const data = await res.json();
      addTeacherMessage(data.reply);
      history.push({ role: "teacher", content: data.reply });
      if (data.mood) setMood(data.mood);
    }
  } catch (err) {
    removeTyping();
  } finally {
    sendBtnEl.disabled = false;
    inputEl.focus();
  }
});

/* ---- end session ---- */
document.getElementById("end-btn").addEventListener("click", () => {
  if (confirm("End this session and return to the library?")) {
    sessionStorage.removeItem("mindheist_blueprint");
    window.location.href = "/";
  }
});

/* ============================================================
   INIT — render opening message from blueprint
============================================================ */
(function init() {
  const firstPhase = blueprint.phases[0];
  if (firstPhase) {
    addDayMarker("Scene I · " + firstPhase.name);
  }

  if (blueprint.opening && blueprint.opening.first_line) {
    addTeacherMessage(blueprint.opening.first_line);
    history.push({ role: "teacher", content: blueprint.opening.first_line });
  }

  transcriptEl.scrollTop = transcriptEl.scrollHeight;
  inputEl.focus();
})();

