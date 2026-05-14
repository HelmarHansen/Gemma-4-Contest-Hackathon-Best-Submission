/* chat.js — MindHeist Session */

"use strict";

/* ============================================================
   MOOD ENGINE
============================================================ */
const MOOD_CONFIG = JSON.parse(
  document.getElementById("mood-config").textContent
);
const VAR_MAP = {
  bg: "--bg", surface: "--surface", surface2: "--surface-2",
  ink: "--ink", inkDim: "--ink-dim", inkMute: "--ink-mute",
  line: "--line", accent: "--accent", accent2: "--accent-2",
  glow: "--glow", ambient: "--ambient",
  userBubble: "--user-bubble", userInk: "--user-ink",
  teacherBubble: "--teacher-bubble", teacherInk: "--teacher-ink",
  teacherAccent: "--teacher-accent",
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

window.MindHeist = { setMood, getMoods: () => Object.keys(MOOD_CONFIG.moods) };
setMood(MOOD_CONFIG.active || "neutral");

/* ============================================================
   MUSIC ENGINE
   Phase-driven procedural ambient piano using Web Audio API.
   Classroom-safe: max master gain 0.08, default muted, starts
   only after first user gesture (Web Audio autoplay policy).
============================================================ */
const MusicEngine = (() => {
  // Per-phase: tempo (bpm), melodic scale, bass roots, rhythmic step, voices, mood color
  const PHASES = [
    { bpm: 52,  notes: [220.0, 261.6, 293.7, 349.2, 392.0, 523.3],
      bass:  [110.0, 87.3], step: 6, vol: 0.06, padVol: 0.025, bassVol: 0.05, bright: 800  }, // Setup
    { bpm: 64,  notes: [233.1, 277.2, 329.6, 369.9, 440.0, 554.4],
      bass:  [116.5, 92.5], step: 5, vol: 0.07, padVol: 0.03, bassVol: 0.06, bright: 1100 }, // Investigation
    { bpm: 78,  notes: [246.9, 311.1, 370.0, 415.3, 493.9, 587.3],
      bass:  [123.5, 98.0], step: 4, vol: 0.075, padVol: 0.035, bassVol: 0.07, bright: 1400 }, // Complication
    { bpm: 92,  notes: [261.6, 329.6, 392.0, 440.0, 523.3, 622.3],
      bass:  [130.8, 103.8], step: 3, vol: 0.08, padVol: 0.04, bassVol: 0.075, bright: 1700 }, // Breakthrough
    { bpm: 108, notes: [277.2, 329.6, 415.3, 466.2, 554.4, 659.3],
      bass:  [138.6, 110.0], step: 2, vol: 0.085, padVol: 0.045, bassVol: 0.085, bright: 2000 }, // Confrontation
  ];
  const MAX_GAIN = 0.32;

  let ctx = null, master = null, reverb = null, filter = null;
  let ticker = null, nextBeat = 0, beat = 0;
  let phase = 0, muted = false, started = false;
  let prevMelodyIdx = 0;
  let padOsc1 = null, padOsc2 = null, padGain = null;

  function buildReverb(c) {
    const frames = c.sampleRate * 2.4;
    const buf = c.createBuffer(2, frames, c.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = buf.getChannelData(ch);
      for (let i = 0; i < frames; i++)
        d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / frames, 2.8);
    }
    const node = c.createConvolver();
    node.buffer = buf;
    return node;
  }

  // Melodic note with soft attack, long tail
  function tone(freq, time, volScale = 1.0) {
    const cfg = PHASES[phase];
    const dur = (60 / cfg.bpm) * 3.2;
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = "triangle";
    osc.frequency.value = freq;
    env.gain.setValueAtTime(0, time);
    env.gain.linearRampToValueAtTime(cfg.vol * volScale, time + 0.012);
    env.gain.exponentialRampToValueAtTime(cfg.vol * volScale * 0.22, time + 0.22);
    env.gain.exponentialRampToValueAtTime(0.0001, time + dur);
    osc.connect(env);
    env.connect(reverb);
    env.connect(filter);
    osc.start(time);
    osc.stop(time + dur + 0.05);
  }

  // Bass note with slow attack, sub-bass weight
  function bassTone(freq, time) {
    const cfg = PHASES[phase];
    const dur = (60 / cfg.bpm) * 6.0;
    const osc = ctx.createOscillator();
    const sub = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = "sine";
    sub.type = "sine";
    osc.frequency.value = freq;
    sub.frequency.value = freq * 0.5;
    env.gain.setValueAtTime(0, time);
    env.gain.linearRampToValueAtTime(cfg.bassVol, time + 0.08);
    env.gain.exponentialRampToValueAtTime(0.0001, time + dur);
    osc.connect(env);
    sub.connect(env);
    env.connect(filter);
    osc.start(time); sub.start(time);
    osc.stop(time + dur + 0.05); sub.stop(time + dur + 0.05);
  }

  // Soft chord pad - continuous drone
  function startPad() {
    if (padGain) return;
    const cfg = PHASES[phase];
    padOsc1 = ctx.createOscillator();
    padOsc2 = ctx.createOscillator();
    padGain = ctx.createGain();
    padOsc1.type = "sawtooth";
    padOsc2.type = "sawtooth";
    padOsc1.frequency.value = cfg.notes[0];
    padOsc2.frequency.value = cfg.notes[2] * 0.5;
    padOsc1.detune.value = -7;
    padOsc2.detune.value = +5;
    padGain.gain.value = 0;
    padGain.gain.linearRampToValueAtTime(cfg.padVol, ctx.currentTime + 4.0);
    padOsc1.connect(padGain);
    padOsc2.connect(padGain);
    padGain.connect(filter);
    padOsc1.start(); padOsc2.start();
  }

  function updatePad() {
    if (!padGain) return;
    const cfg = PHASES[phase];
    padOsc1.frequency.setTargetAtTime(cfg.notes[0], ctx.currentTime, 1.5);
    padOsc2.frequency.setTargetAtTime(cfg.notes[2] * 0.5, ctx.currentTime, 1.5);
    padGain.gain.setTargetAtTime(cfg.padVol, ctx.currentTime, 1.5);
    filter.frequency.setTargetAtTime(cfg.bright, ctx.currentTime, 1.5);
  }

  function tick() {
    const cfg     = PHASES[phase];
    const beatSec = 60 / cfg.bpm;
    while (nextBeat < ctx.currentTime + 0.20) {
      // Melody - varied steps (not random, walking) so it sounds composed
      if (beat % cfg.step === 0) {
        const drift = (Math.random() < 0.55) ? 1 : -1;
        let next = prevMelodyIdx + drift * (1 + (Math.random() < 0.25 ? 1 : 0));
        if (next < 0) next = 1;
        if (next >= cfg.notes.length) next = cfg.notes.length - 2;
        prevMelodyIdx = next;
        tone(cfg.notes[next], nextBeat);

        // Chord harmony on structural beats - third + fifth
        if (beat % (cfg.step * 4) === 0) {
          const third = (next + 2) % cfg.notes.length;
          const fifth = (next + 4) % cfg.notes.length;
          tone(cfg.notes[third], nextBeat + 0.020, 0.55);
          tone(cfg.notes[fifth], nextBeat + 0.040, 0.40);
        }
      }
      // Bass - every 2 structural beats, alternating root/fifth
      if (beat % (cfg.step * 2) === 0) {
        const bassNote = cfg.bass[(beat / (cfg.step * 2)) % cfg.bass.length | 0];
        bassTone(bassNote, nextBeat);
      }
      nextBeat += beatSec;
      beat++;
    }
  }

  function setup() {
    ctx    = new (window.AudioContext || window.webkitAudioContext)();
    master = ctx.createGain();
    master.gain.value = 0;
    filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = PHASES[phase].bright;
    filter.Q.value = 0.5;
    reverb = buildReverb(ctx);
    filter.connect(reverb);
    filter.connect(master);     // dry path
    reverb.connect(master);     // wet path
    master.connect(ctx.destination);
  }

  return {
    start() {
      if (!started) {
        started  = true;
        setup();
        startPad();
        nextBeat = ctx.currentTime + 0.3;
        ticker   = setInterval(tick, 50);
      }
      if (ctx.state === "suspended") ctx.resume();
      if (!muted) master.gain.setTargetAtTime(MAX_GAIN, ctx.currentTime, 0.8);
    },
    setPhase(idx) {
      const next = Math.max(0, Math.min(idx, PHASES.length - 1));
      if (next !== phase) {
        phase = next; beat = 0; prevMelodyIdx = 0;
        if (started) updatePad();
      }
    },
    toggleMute() {
      muted = !muted;
      if (master) master.gain.setTargetAtTime(muted ? 0 : MAX_GAIN, ctx.currentTime, 0.6);
      return muted;
    },
    isMuted() { return muted; },
  };
})();

/* ============================================================
   SESSION LOAD
============================================================ */
const _raw = sessionStorage.getItem("mindheist_blueprint");
if (!_raw) {
  window.location.href = "/";
  throw new Error("No session blueprint — redirecting to home");
}
const blueprint = JSON.parse(_raw);

/* ============================================================
   POPULATE SIDEBAR
============================================================ */
const ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X"];

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
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
   SECTION PARSER
   Parses the structured teacher response format:
     [NARRATION], [NPC:Name], [QUESTION], [STATE]
   Returns array of {type, name?, text} sections.
   Falls back gracefully if model uses old [STORY] format.
============================================================ */
function parseSections(text) {
  // Strip [STATE] and anything after
  const stateIdx = text.search(/\[STATE\]/i);
  if (stateIdx !== -1) text = text.slice(0, stateIdx);
  text = text.trim();

  // Legacy [STORY] format fallback
  if (!text.includes("[NARRATION]") && !text.includes("[NPC:")) {
    const stMatch = text.match(/\[STORY\]\s*([\s\S]*?)(?=\[QUESTION\]|$)/i);
    const qMatch  = text.match(/\[QUESTION\]\s*([\s\S]*?)$/i);
    const sections = [];
    const story    = stMatch ? stMatch[1].trim() : text.trim();
    const question = qMatch  ? qMatch[1].trim()  : null;
    if (story)    sections.push({ type: "narration", text: story });
    if (question) sections.push({ type: "question",  text: question });
    return sections;
  }

  // New structured format
  const parts = text.split(/(\[(?:NARRATION|NPC:[^\]]+|QUESTION)\])/i);
  const sections = [];
  let currentType = null;
  let currentName = null;

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    const headerMatch = part.match(/^\[(NARRATION|NPC:([^\]]+)|QUESTION)\]$/i);
    if (headerMatch) {
      const tag = headerMatch[1].toUpperCase();
      if (tag === "NARRATION") {
        currentType = "narration";
        currentName = null;
      } else if (tag === "QUESTION") {
        currentType = "question";
        currentName = null;
      } else {
        currentType = "npc";
        currentName = headerMatch[2]?.trim() || "NPC";
      }
    } else {
      const content = part.trim();
      if (content && currentType) {
        sections.push({ type: currentType, name: currentName, text: content });
      }
    }
  }

  // If parsing produced nothing, treat entire text as narration
  if (sections.length === 0 && text) {
    sections.push({ type: "narration", text: text });
  }
  return sections;
}

/* ============================================================
   RENDERING
============================================================ */
const TEACHER_ICON =
  `<svg viewBox="0 0 100 100" fill="currentColor" aria-hidden="true">` +
  `<circle cx="50" cy="38" r="18"/>` +
  `<path d="M16 100c0-20 15-36 34-36s34 16 34 36z"/>` +
  `</svg>`;

function nowHHMM() {
  const d = new Date();
  return String(d.getHours()).padStart(2, "0") + ":" +
         String(d.getMinutes()).padStart(2, "0");
}

function scrollBottom(transcriptEl) {
  requestAnimationFrame(() =>
    transcriptEl.scrollTo({ top: transcriptEl.scrollHeight, behavior: "smooth" })
  );
}

function addDayMarker(text, feedEl) {
  const el = document.createElement("div");
  el.className = "day";
  el.textContent = text;
  feedEl.appendChild(el);
}

function createTeacherShell(feedEl) {
  const el = document.createElement("div");
  el.className = "msg teacher";
  el.innerHTML =
    `<div class="av">${TEACHER_ICON}</div>` +
    `<div class="body">` +
      `<div class="teacher-response"></div>` +
    `</div>`;
  feedEl.appendChild(el);
  return el.querySelector(".teacher-response");
}

function renderSections(sections, container) {
  container.innerHTML = "";
  for (const sec of sections) {
    if (sec.type === "narration") {
      const el = document.createElement("div");
      el.className = "narration";
      el.textContent = sec.text;
      container.appendChild(el);
    } else if (sec.type === "npc") {
      const block = document.createElement("div");
      block.className = "npc-block";
      block.innerHTML =
        `<div class="npc-name-tag">${escapeHtml(sec.name || "NPC")}</div>` +
        `<div class="npc-bubble"></div>`;
      block.querySelector(".npc-bubble").textContent = sec.text;
      container.appendChild(block);
    } else if (sec.type === "question") {
      const el = document.createElement("div");
      el.className = "practice-question";
      el.textContent = sec.text;
      container.appendChild(el);
    }
  }
}

function addTeacherMessage(text, feedEl) {
  const container = createTeacherShell(feedEl);
  const sections = parseSections(text);
  renderSections(sections, container);
  return container;
}

function addUserMessage(text, feedEl) {
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
}

function showTypingIndicator(feedEl) {
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
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

/* ============================================================
   STREAMING PARSER
   Parses the response line by line while streaming.
   Detects section headers and routes text to the correct DOM element.
============================================================ */
function createStreamParser(responseContainer, transcriptEl) {
  let lineBuffer = "";
  let mode = null;      // "narration" | "npc" | "question" | "state"
  let stateNext = false;
  let currentEl = null;
  let currentNpcBlock = null;

  function getOrCreateNarration() {
    const el = document.createElement("div");
    el.className = "narration";
    responseContainer.appendChild(el);
    return el;
  }

  function getOrCreateNpcBubble(name) {
    const block = document.createElement("div");
    block.className = "npc-block";
    block.innerHTML =
      `<div class="npc-name-tag">${escapeHtml(name)}</div>` +
      `<div class="npc-bubble"></div>`;
    responseContainer.appendChild(block);
    return block.querySelector(".npc-bubble");
  }

  function getOrCreateQuestion() {
    const el = document.createElement("div");
    el.className = "practice-question";
    responseContainer.appendChild(el);
    return el;
  }

  function processLine(line) {
    const trimmed = line.trim();

    if (stateNext) {
      return; // Discard state value
    }

    // Detect section headers
    if (trimmed === "[NARRATION]") {
      mode = "narration";
      currentEl = getOrCreateNarration();
      return;
    }
    if (trimmed === "[QUESTION]") {
      mode = "question";
      currentEl = getOrCreateQuestion();
      return;
    }
    if (trimmed === "[STATE]") {
      mode = "state";
      stateNext = true;
      return;
    }
    const npcMatch = trimmed.match(/^\[NPC:([^\]]+)\]$/i);
    if (npcMatch) {
      mode = "npc";
      currentEl = getOrCreateNpcBubble(npcMatch[1].trim());
      return;
    }

    // Skip inline [STATE] SIGNAL lines
    if (/^\[STATE\][:\s]*(ADVANCE|STAY|CLOSE)/i.test(trimmed)) {
      return;
    }

    // Regular text: append to current section element
    if (currentEl && mode !== "state") {
      currentEl.textContent += line + "\n";
      scrollBottom(transcriptEl);
    } else if (mode === null && line.trim()) {
      // Text before any header — treat as narration
      mode = "narration";
      currentEl = getOrCreateNarration();
      currentEl.textContent += line + "\n";
      scrollBottom(transcriptEl);
    }
  }

  return {
    push(chunk) {
      lineBuffer += chunk;
      let pos;
      while ((pos = lineBuffer.indexOf("\n")) !== -1) {
        const line = lineBuffer.slice(0, pos);
        lineBuffer = lineBuffer.slice(pos + 1);
        processLine(line);
      }
      // Flush partial line if safe (doesn't start a potential header)
      if (lineBuffer && !lineBuffer.startsWith("[") && currentEl && mode !== "state") {
        currentEl.textContent += lineBuffer;
        lineBuffer = "";
        scrollBottom(transcriptEl);
      }
    },
    flush() {
      // Flush any remaining buffered text
      if (lineBuffer && currentEl && mode !== "state") {
        currentEl.textContent += lineBuffer;
        lineBuffer = "";
      }
    },
  };
}

/* ============================================================
   DEBUG COMMAND HANDLER
   Intercepts messages starting with "/" in both tabs.
   All commands hit the /api/debug/* endpoints — no model calls.
============================================================ */
async function handleCommand(text, feedTarget, scrollTarget) {
  const parts = text.trim().split(/\s+/);
  const cmd   = parts[0].toLowerCase();
  
  function dbg(title, lines) {
    const el = document.createElement("div");
    el.className = "debug-msg";
    el.innerHTML =
      `<div class="debug-title">${escapeHtml(title)}</div>` +
      lines.map(l => `<div class="debug-line">${escapeHtml(String(l))}</div>`).join("");
    feedTarget.appendChild(el);
    scrollBottom(scrollTarget);
  }

  if (cmd === "/help" || cmd === "/?") {
    dbg("Debug Commands", [
      "/status      — session state (turn, phase, move)",
      "/move        — active move details",
      "/answer      — expected answer for current move",
      "/hint        — hint for current move",
      "/moves       — list all move IDs",
      "/skip        — force ADVANCE (skip current move)",
      "/goto <id>   — jump to move by ID",
      "/unlock      — unlock all characters for interrogation",
      "/phase       — current phase info",
      "/chars       — list all characters + unlock status",
      "/solution    — show full solution (all expected answers)",
      "/end         — force CLOSE the session",
    ]);
    return;
  }

  const sid = blueprint.session_id;

  if (cmd === "/status") {
    try {
      const res = await fetch(`/api/debug/${sid}/state`);
      const d = await res.json();
      const s = d.state;
      dbg("Session Status", [
        `session_id:   ${sid}`,
        `turn:         ${s.turn_count} / ${blueprint.session.estimated_turns}`,
        `correct:      ${s.correct_count}`,
        `current_move: ${s.current_move_id}`,
        `closed:       ${s.closed}`,
        `visited:      ${s.visited_move_ids.join(", ") || "(none)"}`,
      ]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/move") {
    try {
      const res = await fetch(`/api/debug/${sid}/state`);
      const d = await res.json();
      const m = d.current_move;
      if (!m) { dbg("Move", ["No active move"]); return; }
      dbg("Active Move", [
        `id:       ${m.id}`,
        `phase:    ${m.phase}`,
        `type:     ${m.type}`,
        `trigger:  ${m.trigger}`,
        `content:  ${m.content.slice(0, 120)}${m.content.length > 120 ? "…" : ""}`,
      ]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/answer") {
    try {
      const res = await fetch(`/api/debug/${sid}/state`);
      const d = await res.json();
      const m = d.current_move;
      if (!m) { dbg("Answer", ["No active move"]); return; }
      dbg("Expected Answer", [
        `move: ${m.id}`,
        m.source_ref   ? `source: ${m.source_ref}` : "",
        m.is_error_trap ? `⚠ error trap — correct value: ${m.error_correction_key || "?"}` : "",
        "",
        m.expected_student_response,
      ].filter(Boolean));
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/moves") {
    try {
      const res = await fetch(`/api/debug/${sid}/state`);
      const d = await res.json();
      dbg("All Moves", d.blueprint_summary.move_ids.map((id, i) =>
        `${String(i + 1).padStart(2, "0")}. ${id}${id === d.state.current_move_id ? " ← active" : ""}`
      ));
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/skip") {
    try {
      const res = await fetch(`/api/debug/${sid}/advance`, { method: "POST" });
      const d = await res.json();
      dbg("Skipped", [`→ ${d.new_move_id}`, d.closed ? "Session closed." : ""]);
      if (d.closed) closeSession(null);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/goto") {
    const moveId = parts[1];
    if (!moveId) { dbg("Usage", ["/goto <move_id>"]); return; }
    try {
      const res = await fetch(`/api/debug/${sid}/goto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ move_id: moveId }),
      });
      const d = await res.json();
      if (!res.ok) { dbg("Error", [d.detail]); return; }
      dbg("Jumped", [`→ ${d.current_move_id}`]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/unlock") {
    try {
      const res = await fetch(`/api/debug/${sid}/unlock_chars`, { method: "POST" });
      const d = await res.json();
      updateAppearedCharacters(d.unlocked);
      dbg("Unlocked Characters", d.unlocked.length ? d.unlocked : ["(none)"]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/phase") {
    try {
      const res = await fetch(`/api/debug/${sid}/state`);
      const d = await res.json();
      const moves = blueprint.moves || [];
      const currentMove = moves.find(m => m.id === d.state.current_move_id);
      const phaseIdx = blueprint.phases.findIndex(p => currentMove && p.id === currentMove.phase);
      const phase = phaseIdx >= 0 ? blueprint.phases[phaseIdx] : null;
      if (!phase) { dbg("Phase", ["Unknown"]); return; }
      dbg("Current Phase", [
        `index: ${phaseIdx + 1} / ${blueprint.phases.length}`,
        `id:    ${phase.id}`,
        `name:  ${phase.name}`,
        `goal:  ${phase.goal}`,
      ]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/chars") {
    const chars = blueprint.characters || [];
    if (!chars.length) { dbg("Characters", ["(none in blueprint)"]); return; }
    dbg("Characters", chars.map(c =>
      `${appearedCharacterIds.has(c.id) ? "✓" : "✗"} ${c.id} — ${c.name} (${c.role})`
    ));
    return;
  }

  if (cmd === "/hint") {
    try {
      const res = await fetch(`/api/debug/${sid}/state`);
      const d = await res.json();
      const m = d.current_move;
      if (!m) { dbg("Hint", ["No active move"]); return; }
      dbg("Hint", [
        `move: ${m.id}`,
        m.hint || "(no hint available)",
      ]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  if (cmd === "/solution") {
    const moves = blueprint.moves || [];
    if (!moves.length) { dbg("Solution", ["(no moves)"]); return; }
    dbg("Full Solution", moves.map((m, i) =>
      `${String(i + 1).padStart(2, "0")}. [${m.id}] ${m.expected_student_response}`
    ));
    return;
  }

  if (cmd === "/end") {
    try {
      // Use advance repeatedly until closing — simpler: just navigate to the closing move
      const closingMove = (blueprint.moves || []).find(m => m.type === "closing");
      if (!closingMove) { dbg("End", ["No closing move found"]); return; }
      const res = await fetch(`/api/debug/${sid}/goto`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ move_id: closingMove.id }),
      });
      const d = await res.json();
      if (!res.ok) { dbg("Error", [d.detail]); return; }
      dbg("Ended", [`Jumped to closing move: ${closingMove.id}`, "Answer correctly to trigger CLOSE."]);
    } catch (e) { dbg("Error", [e.message]); }
    return;
  }

  dbg("Unknown command", [`'${cmd}' — type /help for a list`]);
}

/* ============================================================
   CHAT ENGINE — INVESTIGATION TAB
============================================================ */
const feedEl        = document.getElementById("feed");
const transcriptEl  = document.getElementById("transcript");
const inputEl       = document.getElementById("composer-input");
const sendBtnEl     = document.getElementById("send-btn");

const history = [];
let currentPhaseIndex = 0;
let currentTurn = 1;
let isSending = false;

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
sendBtnEl.addEventListener("click", sendMessage);

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || isSending) return;

  if (text.startsWith("/")) {
    inputEl.value = "";
    inputEl.style.height = "auto";
    await handleCommand(text, feedEl, transcriptEl);
    return;
  }

  MusicEngine.start();
  addUserMessage(text, feedEl);
  const historySnapshot = history.slice();
  history.push({ role: "user", content: text });

  inputEl.value = "";
  inputEl.style.height = "auto";
  isSending = true;
  sendBtnEl.disabled = true;

  showTypingIndicator(feedEl);
  scrollBottom(transcriptEl);

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: blueprint.session_id,
        message: text,
        history: historySnapshot,
      }),
    });

    if (!response.ok) {
      removeTypingIndicator();
      const err = await response.json().catch(() => ({}));
      addTeacherMessage("[Error: " + (err.detail || response.statusText) + "]", feedEl);
      return;
    }

    // Typing indicator stays until the first content chunk arrives
    let responseContainer = null;
    let parser = null;
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let sseBuffer = "";
    let fullRawText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });
      const events = sseBuffer.split("\n\n");
      sseBuffer = events.pop(); // Keep incomplete last event

      for (const event of events) {
        const line = event.trim();
        if (!line.startsWith("data: ")) continue;
        let data;
        try { data = JSON.parse(line.slice(6)); } catch { continue; }

        if (data.error) {
          removeTypingIndicator();
          addTeacherMessage("[Error: " + data.error + "]", feedEl);
          return;
        }

        if (data.chunk) {
          // First chunk — swap typing indicator for streaming container
          if (!responseContainer) {
            removeTypingIndicator();
            responseContainer = createTeacherShell(feedEl);
            parser = createStreamParser(responseContainer, transcriptEl);
          }
          fullRawText += data.chunk;
          parser.push(data.chunk);
        }

        if (data.done) {
          parser.flush();
          history.push({ role: "teacher", content: fullRawText });
          currentTurn++;
          updateTurnCounter(currentTurn);

          if (data.mood) setMood(data.mood);

          if (typeof data.phase_index === "number" && data.phase_index !== currentPhaseIndex) {
            currentPhaseIndex = data.phase_index;
            updateActiveScene(currentPhaseIndex);
            MusicEngine.setPhase(currentPhaseIndex);
            const phase = blueprint.phases[currentPhaseIndex];
            if (phase) {
              addDayMarker(
                "Scene " + (ROMAN[currentPhaseIndex] || currentPhaseIndex + 1) +
                " · " + phase.name,
                feedEl
              );
            }
          }

          if (data.appeared_character_ids) {
            updateAppearedCharacters(data.appeared_character_ids);
          }

          if (data.closed) {
            closeSession(data.closing_line);
          }
        }
      }
    }

  } catch (err) {
    removeTypingIndicator();
    addTeacherMessage("[Connection error: " + err.message + "]", feedEl);
  } finally {
    isSending = false;
    sendBtnEl.disabled = false;
    inputEl.focus();
  }
}

/* ---- hint button ---- */
document.getElementById("hint-btn").addEventListener("click", async () => {
  if (isSending) return;
  isSending = true;
  sendBtnEl.disabled = true;
  showTypingIndicator(feedEl);

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: blueprint.session_id,
        message: "[SYSTEM: The detective is stuck. Introduce a new in-story detail — a smell, a prop, a nervous gesture from an NPC, an overheard phrase — that nudges them toward the right knowledge without stating it directly. Stay in character.]",
        history: history.slice(),
      }),
    });
    removeTypingIndicator();
    if (res.ok) {
      const data = await res.json();
      addTeacherMessage(data.reply, feedEl);
      history.push({ role: "teacher", content: data.reply });
      if (data.mood) setMood(data.mood);
      if (data.appeared_character_ids) updateAppearedCharacters(data.appeared_character_ids);
    }
  } catch (err) {
    removeTypingIndicator();
  } finally {
    isSending = false;
    sendBtnEl.disabled = false;
    inputEl.focus();
  }
});

/* ---- scene / turn updates ---- */
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

/* ---- closing sequence ---- */
function closeSession(closingLine) {
  inputEl.disabled = true;
  sendBtnEl.disabled = true;
  document.getElementById("hint-btn").disabled = true;

  addDayMarker("Case closed", feedEl);

  if (closingLine) {
    const el = document.createElement("div");
    el.className = "msg teacher closing";
    el.innerHTML =
      `<div class="av">${TEACHER_ICON}</div>` +
      `<div class="body">` +
        `<div class="teacher-response">` +
          `<div class="npc-bubble bubble-closing">${escapeHtml(closingLine)}</div>` +
        `</div>` +
      `</div>`;
    feedEl.appendChild(el);
    scrollBottom(transcriptEl);
  }

  const bar = document.getElementById("investigation-composer");
  const returnBtn = document.createElement("a");
  returnBtn.href = "/";
  returnBtn.className = "btn btn-return";
  returnBtn.textContent = "Return to library";
  bar.appendChild(returnBtn);
}

/* ---- music button ---- */
const musicBtn = document.getElementById("music-btn");
musicBtn.addEventListener("click", () => {
  MusicEngine.start(); // creates AudioContext on first click (satisfies autoplay policy)
  const nowMuted = MusicEngine.toggleMute();
  musicBtn.classList.toggle("muted", nowMuted);
});

/* ---- end session button ---- */
document.getElementById("end-btn").addEventListener("click", () => {
  if (confirm("End this session and return to the library?")) {
    sessionStorage.removeItem("mindheist_blueprint");
    window.location.href = "/";
  }
});

/* ============================================================
   TAB SWITCHING
============================================================ */
const tabInvestigationBtn = document.getElementById("tab-investigation-btn");
const tabInterrogationBtn = document.getElementById("tab-interrogation-btn");
const panelInvestigation  = document.getElementById("panel-investigation");
const panelInterrogation  = document.getElementById("panel-interrogation");

function switchTab(tab) {
  if (tab === "investigation") {
    tabInvestigationBtn.classList.add("active");
    tabInvestigationBtn.setAttribute("aria-selected", "true");
    tabInterrogationBtn.classList.remove("active");
    tabInterrogationBtn.setAttribute("aria-selected", "false");
    panelInvestigation.classList.add("active");
    panelInterrogation.classList.remove("active");
    inputEl.focus();
  } else {
    tabInterrogationBtn.classList.add("active");
    tabInterrogationBtn.setAttribute("aria-selected", "true");
    tabInvestigationBtn.classList.remove("active");
    tabInvestigationBtn.setAttribute("aria-selected", "false");
    panelInterrogation.classList.add("active");
    panelInvestigation.classList.remove("active");
  }
}

tabInvestigationBtn.addEventListener("click", () => switchTab("investigation"));
tabInterrogationBtn.addEventListener("click", () => switchTab("interrogation"));

/* ============================================================
   INTERROGATION TAB
============================================================ */
const charSelectorBar      = document.getElementById("char-selector-bar");
const noCharsMsg           = document.getElementById("no-chars-msg");
const interrogationFeed    = document.getElementById("interrogation-feed");
const interrogationTranscript = document.getElementById("interrogation-transcript");
const interrogationInput   = document.getElementById("interrogation-input");
const interrogationSendBtn = document.getElementById("interrogation-send-btn");
const interrogationPlaceholder = document.getElementById("interrogation-placeholder");

let selectedCharacterId = null;
let isInterrogating = false;
const characterHistories = new Map(); // characterId → [{role, content}]
let appearedCharacterIds = new Set();

function getInitials(name) {
  return name.split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
}

function updateAppearedCharacters(ids) {
  const prev = appearedCharacterIds.size;
  if (ids && ids.length) {
    ids.forEach(id => appearedCharacterIds.add(id));
  }
  // Always rebuild so locked cards show from turn 1
  rebuildCharacterSelector();
  // Update badge
  const badge = document.getElementById("char-count-badge");
  badge.textContent = String(appearedCharacterIds.size);
  if (appearedCharacterIds.size > prev && prev === 0) {
    if (noCharsMsg) noCharsMsg.style.display = "none";
  }
}

// Render the locked character cards immediately on page load
if (blueprint.characters && blueprint.characters.length) {
  rebuildCharacterSelector();
  if (noCharsMsg) noCharsMsg.textContent = "Characters will unlock as you investigate";
}

function rebuildCharacterSelector() {
  // Remove existing char cards
  charSelectorBar.querySelectorAll(".char-card").forEach(el => el.remove());

  const chars = blueprint.characters || [];
  const hasAppeared = chars.some(c => appearedCharacterIds.has(c.id));

  if (hasAppeared) {
    noCharsMsg.style.display = "none";
  }

  chars.forEach(char => {
    const unlocked = appearedCharacterIds.has(char.id);
    const card = document.createElement("div");
    card.className = "char-card" +
      (!unlocked ? " locked" : "") +
      (char.id === selectedCharacterId ? " active" : "");
    card.dataset.charId = char.id;
    card.innerHTML =
      `<div class="char-card-initials">${escapeHtml(getInitials(char.name))}</div>` +
      `<div class="char-card-name">${escapeHtml(char.name)}</div>` +
      `<div class="char-card-role">${escapeHtml(char.role)}</div>`;

    if (unlocked) {
      card.addEventListener("click", () => selectCharacter(char.id));
    }
    charSelectorBar.appendChild(card);
  });
}

function selectCharacter(charId) {
  selectedCharacterId = charId;

  // Update card active states
  charSelectorBar.querySelectorAll(".char-card").forEach(el => {
    el.classList.toggle("active", el.dataset.charId === charId);
  });

  const char = (blueprint.characters || []).find(c => c.id === charId);
  if (!char) return;

  // Restore or clear chat history for this character
  if (interrogationPlaceholder) interrogationPlaceholder.remove();
  interrogationFeed.innerHTML = "";

  const hist = characterHistories.get(charId) || [];
  if (hist.length === 0) {
    addDayMarker("Interrogating " + char.name, interrogationFeed);
  } else {
    // Re-render existing history
    addDayMarker("Interrogating " + char.name, interrogationFeed);
    hist.forEach(msg => {
      if (msg.role === "user") {
        addUserMessage(msg.content, interrogationFeed);
      } else {
        addNpcMessage(char.name, msg.content, interrogationFeed);
      }
    });
  }

  interrogationInput.disabled = false;
  interrogationInput.placeholder = "Ask " + char.name + "…";
  interrogationSendBtn.disabled = false;
  interrogationInput.focus();
  scrollBottom(interrogationTranscript);
}

function addNpcMessage(charName, text, feedTarget) {
  const initials = getInitials(charName);
  const el = document.createElement("div");
  el.className = "msg teacher npc-msg";
  el.innerHTML =
    `<div class="av">${escapeHtml(initials)}</div>` +
    `<div class="body">` +
      `<div class="meta">` +
        `<span class="name" style="font-family:inherit;font-size:13px;font-style:normal;">${escapeHtml(charName)}</span>` +
        `<span class="time">${nowHHMM()}</span>` +
      `</div>` +
      `<div class="teacher-response"><div class="npc-bubble"></div></div>` +
    `</div>`;
  el.querySelector(".npc-bubble").textContent = text;
  feedTarget.appendChild(el);
  scrollBottom(interrogationTranscript);
}

interrogationInput.addEventListener("input", () => {
  interrogationInput.style.height = "auto";
  interrogationInput.style.height = Math.min(interrogationInput.scrollHeight, 200) + "px";
});

interrogationInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendInterrogation();
  }
});
interrogationSendBtn.addEventListener("click", sendInterrogation);

async function sendInterrogation() {
  const text = interrogationInput.value.trim();
  if (!text || isInterrogating || !selectedCharacterId) return;

  if (text.startsWith("/")) {
    interrogationInput.value = "";
    interrogationInput.style.height = "auto";
    await handleCommand(text, interrogationFeed, interrogationTranscript);
    return;
  }

  const char = (blueprint.characters || []).find(c => c.id === selectedCharacterId);
  if (!char) return;

  addUserMessage(text, interrogationFeed);
  const hist = characterHistories.get(selectedCharacterId) || [];
  hist.push({ role: "user", content: text });
  characterHistories.set(selectedCharacterId, hist);

  interrogationInput.value = "";
  interrogationInput.style.height = "auto";
  isInterrogating = true;
  interrogationSendBtn.disabled = true;

  // Typing indicator in interrogation feed
  const typingEl = document.createElement("div");
  typingEl.className = "msg teacher";
  typingEl.id = "interrogation-typing";
  typingEl.innerHTML =
    `<div class="av">${escapeHtml(getInitials(char.name))}</div>` +
    `<div class="body">` +
      `<div class="typing"><span></span><span></span><span></span></div>` +
    `</div>`;
  interrogationFeed.appendChild(typingEl);
  scrollBottom(interrogationTranscript);

  try {
    const res = await fetch("/api/interrogate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id:   blueprint.session_id,
        character_id: selectedCharacterId,
        message:      text,
        history:      hist.slice(0, -1), // history before current message
      }),
    });

    const typing = document.getElementById("interrogation-typing");
    if (typing) typing.remove();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      addNpcMessage(char.name, "[Error: " + (err.detail || res.statusText) + "]", interrogationFeed);
      return;
    }

    const data = await res.json();
    addNpcMessage(char.name, data.reply, interrogationFeed);
    hist.push({ role: "npc", content: data.reply });
    characterHistories.set(selectedCharacterId, hist);

  } catch (err) {
    const typing = document.getElementById("interrogation-typing");
    if (typing) typing.remove();
    addNpcMessage(char.name, "[Connection error: " + err.message + "]", interrogationFeed);
  } finally {
    isInterrogating = false;
    interrogationSendBtn.disabled = false;
    interrogationInput.focus();
  }
}

/* ============================================================
   INIT — fetch session state, render opening message
============================================================ */
(async function init() {
  // Fetch appeared characters from server (in case session was resumed)
  try {
    const res = await fetch("/api/session/" + blueprint.session_id);
    if (res.ok) {
      const data = await res.json();
      if (data.appeared_character_ids?.length) {
        updateAppearedCharacters(data.appeared_character_ids);
      }
    }
  } catch { /* ignore, not critical */ }

  // Pre-populate all characters so they appear locked until met
  rebuildCharacterSelector();

  // Render opening message
  const firstPhase = blueprint.phases[0];
  if (firstPhase) {
    addDayMarker("Scene I · " + firstPhase.name, feedEl);
  }

  if (blueprint.opening?.first_line) {
    addTeacherMessage(blueprint.opening.first_line, feedEl);
    history.push({ role: "teacher", content: blueprint.opening.first_line });
  }

  scrollBottom(transcriptEl);
  inputEl.focus();
})();
