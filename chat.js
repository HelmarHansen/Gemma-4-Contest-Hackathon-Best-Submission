"use strict";

/* =========================================================================
   MindHeist — Chat UI
   Two functional tabs: Investigation (game-master) and Interrogation (NPCs).
   ========================================================================= */

const raw = sessionStorage.getItem("mindheist_blueprint");
if (!raw) {
  window.location.href = "/";
  throw new Error("No blueprint found");
}
let blueprint;
try {
  blueprint = JSON.parse(raw);
} catch (e) {
  // Corrupted blob — wipe and bounce so the user can regenerate, instead of
  // leaving every DOM binding below unattached because the script crashed.
  sessionStorage.removeItem("mindheist_blueprint");
  window.location.href = "/";
  throw new Error("Stored blueprint is not valid JSON: " + e.message);
}

/* postWithRestore: if the backend has forgotten this session (e.g. it was
   restarted between case-generation and chat), re-register the in-memory
   blueprint and retry once. Without this, every /api/chat call returns 404
   and the user just sees the fallback message every time. */
async function postWithRestore(url, body) {
  const init = {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(body),
  };
  let res = await fetch(url, init);
  if (res.status === 404) {
    try {
      await fetch("/api/session/restore", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(blueprint),
      });
    } catch (_) { /* fall through and surface the original 404 */ }
    res = await fetch(url, init);
  }
  return res;
}

/* ---------- utils ---------- */

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function nowHHMM() {
  const d = new Date();
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

function scrollBottom(el) {
  if (!el) return;
  requestAnimationFrame(() =>
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" })
  );
}

function initials(name) {
  return String(name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("") || "?";
}

/* ---------- DOM references ---------- */

const dom = {
  // header
  teacherName:        document.getElementById("teacher-name"),
  teacherRole:        document.getElementById("teacher-role"),
  // tabs
  tabInvestigation:   document.getElementById("tab-investigation"),
  tabInterrogation:   document.getElementById("tab-interrogation"),
  panelInvestigation: document.getElementById("panel-investigation"),
  panelInterrogation: document.getElementById("panel-interrogation"),
  // sidebar
  sideActs:           document.getElementById("side-acts"),
  sideCharacters:     document.getElementById("side-characters"),
  scenesList:         document.getElementById("scenes-list"),
  charactersList:     document.getElementById("characters-list"),
  // investigation
  feedInv:            document.getElementById("feed-investigation"),
  transcriptInv:      document.getElementById("transcript-investigation"),
  composerInv:        document.getElementById("composer-investigation"),
  sendInv:            document.getElementById("send-investigation"),
  hintBtn:            document.getElementById("hint-btn"),
  micInv:             document.getElementById("mic-investigation"),
  // interrogation
  feedInter:          document.getElementById("feed-interrogation"),
  transcriptInter:    document.getElementById("transcript-interrogation"),
  composerInter:      document.getElementById("composer-interrogation"),
  sendInter:          document.getElementById("send-interrogation"),
  micInter:           document.getElementById("mic-interrogation"),
  interrogationEmpty: document.getElementById("interrogation-empty"),
  interrogationName:  document.getElementById("interrogation-name"),
  interrogationRole:  document.getElementById("interrogation-role"),
  interrogationAv:    document.getElementById("interrogation-avatar"),
  // top
  moodPill:           document.getElementById("mood-pill"),
  moodDot:            document.getElementById("mood-dot"),
  moodLabel:          document.getElementById("mood-label"),
  musicBtn:           document.getElementById("music-btn"),
};

/* =========================================================================
   MOOD + AMBIENT AUDIO  (noir soundscape — fully procedural, no files)

   Each mood drives a small "ensemble":
     • A bass drone (sine + detuned saw, low-pass filtered)
     • A pad chord (3 voices, slow detune wobble)
     • A noise layer (vinyl-crackle / rain) for film grain
     • A sparse melodic ping that plays only in tense/danger moods
   Every layer crossfades between moods in ~4 s so the music never restarts.
   ========================================================================= */

// Mood → musical content. Frequencies are in Hz; chord = 3 voices.
// Mood → musical content + colour used both by the audio engine and the CSS pill.
const MOOD_PRESETS = {
  // calm: minor 9 chord, slow, almost suspended
  calm:    { bass: 65.4,  chord: [196.0, 246.9, 329.6], filter: 900,  noise: 0.020, ping: false, label: "Calm",     accent: "#5b8aa0" },
  // neutral: open fifth, no third
  neutral: { bass: 73.4,  chord: [220.0, 277.2, 329.6], filter: 1100, noise: 0.018, ping: false, label: "Neutral",  accent: "#6b7280" },
  // warm: major triad, slight brightness
  warm:    { bass: 87.3,  chord: [220.0, 277.2, 329.6], filter: 1500, noise: 0.014, ping: false, label: "Warm",     accent: "#b58a4a" },
  // tense: half-diminished, dissonant interval
  tense:   { bass: 73.4,  chord: [220.0, 261.6, 311.1], filter: 1700, noise: 0.030, ping: true,  label: "Tense",    accent: "#9c5a4a" },
  // danger: tritone over low pedal
  danger:  { bass: 55.0,  chord: [185.0, 220.0, 311.1], filter: 2200, noise: 0.046, ping: true,  label: "Danger",   accent: "#8a3a3a" },
};
const MOOD_DEFAULT = "neutral";

const moodAudio = {
  ctx:        null,
  master:     null,
  bassOsc:    null,
  bassSub:    null,
  bassGain:   null,
  bassFilter: null,
  chord:      [],       // { osc, gain }
  noiseSrc:   null,
  noiseGain:  null,
  pingTimer:  null,
  enabled:    true,
  started:    false,
  currentMood: MOOD_DEFAULT,

  async ensure() {
    if (this.ctx) return;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return;
    this.ctx = new Ctor();

    this.master = this.ctx.createGain();
    this.master.gain.value = 0;
    this.master.connect(this.ctx.destination);

    // Bass: sine + slightly detuned sawtooth through a low-pass filter
    this.bassFilter = this.ctx.createBiquadFilter();
    this.bassFilter.type = "lowpass";
    this.bassFilter.frequency.value = 1100;
    this.bassFilter.Q.value = 0.8;
    this.bassFilter.connect(this.master);

    this.bassGain = this.ctx.createGain();
    this.bassGain.gain.value = 0.55;
    this.bassGain.connect(this.bassFilter);

    this.bassOsc = this.ctx.createOscillator();
    this.bassOsc.type = "sine";
    this.bassOsc.frequency.value = 73.4;
    this.bassOsc.connect(this.bassGain);
    this.bassOsc.start();

    this.bassSub = this.ctx.createOscillator();
    this.bassSub.type = "sawtooth";
    this.bassSub.detune.value = -8;
    this.bassSub.frequency.value = 73.4;
    const subGain = this.ctx.createGain();
    subGain.gain.value = 0.18;
    this.bassSub.connect(subGain).connect(this.bassFilter);
    this.bassSub.start();

    // Pad chord: 3 sine voices with slow shimmer
    for (let i = 0; i < 3; i++) {
      const osc = this.ctx.createOscillator();
      osc.type = "sine";
      osc.detune.value = (i - 1) * 6;          // gentle spread
      const g = this.ctx.createGain();
      g.gain.value = 0.20;
      osc.connect(g).connect(this.master);
      // slow LFO on detune for a chorus-like wobble
      const lfo = this.ctx.createOscillator();
      lfo.type = "sine";
      lfo.frequency.value = 0.07 + i * 0.03;
      const lfoGain = this.ctx.createGain();
      lfoGain.gain.value = 5;                  // ± 5 cents
      lfo.connect(lfoGain).connect(osc.detune);
      lfo.start();
      osc.start();
      this.chord.push({ osc, gain: g });
    }

    // Vinyl crackle: pink-ish noise through a band-pass
    const buf = this.ctx.createBuffer(1, this.ctx.sampleRate * 4, this.ctx.sampleRate);
    const ch = buf.getChannelData(0);
    let b0=0,b1=0,b2=0,b3=0,b4=0,b5=0,b6=0;
    for (let i = 0; i < ch.length; i++) {
      const white = Math.random() * 2 - 1;
      // Paul Kellet's pink-noise filter
      b0 = 0.99886*b0 + white*0.0555179;
      b1 = 0.99332*b1 + white*0.0750759;
      b2 = 0.96900*b2 + white*0.1538520;
      b3 = 0.86650*b3 + white*0.3104856;
      b4 = 0.55000*b4 + white*0.5329522;
      b5 = -0.7616*b5 - white*0.0168980;
      ch[i] = (b0+b1+b2+b3+b4+b5+b6+white*0.5362) * 0.11;
      b6 = white * 0.115926;
    }
    this.noiseSrc = this.ctx.createBufferSource();
    this.noiseSrc.buffer = buf;
    this.noiseSrc.loop = true;
    const noiseHP = this.ctx.createBiquadFilter();
    noiseHP.type = "highpass";
    noiseHP.frequency.value = 1500;
    this.noiseGain = this.ctx.createGain();
    this.noiseGain.gain.value = 0.02;
    this.noiseSrc.connect(noiseHP).connect(this.noiseGain).connect(this.master);
    this.noiseSrc.start();
  },

  async start() {
    if (this.started || !this.enabled) return;
    await this.ensure();
    if (!this.ctx) return;
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.started = true;
    this.applyMood(this.currentMood, 2.5);
    this._fadeMaster(0.09, 2.0);
    this._schedulePings();
  },

  stop() {
    if (!this.ctx || !this.started) return;
    this._fadeMaster(0, 0.8);
    this.started = false;
    if (this.pingTimer) clearTimeout(this.pingTimer);
    this.pingTimer = null;
  },

  setEnabled(b) {
    this.enabled = b;
    if (!b) this.stop();
  },

  setMood(name) {
    const mood = MOOD_PRESETS[name] ? name : MOOD_DEFAULT;
    this.currentMood = mood;
    document.body.dataset.mood = mood;
    if (dom.moodLabel) dom.moodLabel.textContent = MOOD_PRESETS[mood].label;
    if (dom.moodDot)   dom.moodDot.style.background = MOOD_PRESETS[mood].accent;
    if (this.started && this.ctx) this.applyMood(mood, 4.0);
  },

  applyMood(mood, fadeSec) {
    if (!this.ctx) return;
    const p = MOOD_PRESETS[mood];
    const t0 = this.ctx.currentTime;
    // Bass
    [this.bassOsc, this.bassSub].forEach(o => {
      o.frequency.cancelScheduledValues(t0);
      o.frequency.setValueAtTime(o.frequency.value, t0);
      o.frequency.linearRampToValueAtTime(p.bass, t0 + fadeSec);
    });
    // Filter
    this.bassFilter.frequency.cancelScheduledValues(t0);
    this.bassFilter.frequency.setValueAtTime(this.bassFilter.frequency.value, t0);
    this.bassFilter.frequency.linearRampToValueAtTime(p.filter, t0 + fadeSec);
    // Chord
    this.chord.forEach((v, i) => {
      const f = p.chord[i] ?? p.chord[p.chord.length - 1];
      v.osc.frequency.cancelScheduledValues(t0);
      v.osc.frequency.setValueAtTime(v.osc.frequency.value, t0);
      v.osc.frequency.linearRampToValueAtTime(f, t0 + fadeSec);
    });
    // Noise level
    this.noiseGain.gain.cancelScheduledValues(t0);
    this.noiseGain.gain.setValueAtTime(this.noiseGain.gain.value, t0);
    this.noiseGain.gain.linearRampToValueAtTime(p.noise, t0 + fadeSec);
  },

  _fadeMaster(target, sec) {
    if (!this.ctx || !this.master) return;
    const t0 = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(t0);
    this.master.gain.setValueAtTime(this.master.gain.value, t0);
    this.master.gain.linearRampToValueAtTime(target, t0 + sec);
  },

  // Sparse single-note melodic punctuation in tense/danger moods.
  _schedulePings() {
    if (!this.ctx || !this.started) return;
    const tick = () => {
      if (!this.started) return;
      const p = MOOD_PRESETS[this.currentMood];
      if (p.ping) this._ping();
      this.pingTimer = setTimeout(tick, 6500 + Math.random() * 5000);
    };
    this.pingTimer = setTimeout(tick, 4500);
  },

  _ping() {
    if (!this.ctx) return;
    const p = MOOD_PRESETS[this.currentMood];
    // pick a chord tone two octaves up
    const baseChoice = p.chord[Math.floor(Math.random() * p.chord.length)];
    const f = baseChoice * 2;
    const osc = this.ctx.createOscillator();
    osc.type = "triangle";
    osc.frequency.value = f;
    const g = this.ctx.createGain();
    const filt = this.ctx.createBiquadFilter();
    filt.type = "lowpass";
    filt.frequency.value = 2200;
    osc.connect(filt).connect(g).connect(this.master);
    const t = this.ctx.currentTime;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(0.18, t + 0.08);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 2.6);
    osc.start(t);
    osc.stop(t + 2.7);
  },
};

function applyMoodFromResponse(data) {
  const mood = data && data.mood;
  if (!mood) return;
  moodAudio.setMood(mood);
}

/* =========================================================================
   SPEECH INPUT — Web Speech API (Chrome / Edge / Safari)
   The browser must run over HTTPS or localhost; otherwise the API refuses.
   We surface a clear toast on permission errors so the user knows what to fix.
   ========================================================================= */

const SRCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

function showMicToast(text) {
  let el = document.getElementById("mic-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "mic-toast";
    el.className = "mic-toast";
    document.body.appendChild(el);
  }
  el.textContent = text;
  el.classList.add("on");
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => el.classList.remove("on"), 3800);
}

function setupMic(btn, textarea, getLang) {
  if (!btn) return;
  if (!SRCtor) {
    btn.disabled = true;
    btn.title = "Voice input not available in this browser. Use Chrome, Edge, or Safari.";
    btn.classList.add("mic-unsupported");
    return;
  }
  let rec = null;
  let listening = false;

  const stop = () => {
    if (listening && rec) {
      try { rec.stop(); } catch (_) {}
    }
  };

  btn.addEventListener("click", async () => {
    if (listening) { stop(); return; }

    // Pre-flight: ask for microphone permission explicitly so the user gets
    // a clear OS-level prompt the first time, instead of a silent failure.
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // We only needed the permission grant; release the stream immediately.
        stream.getTracks().forEach(t => t.stop());
      }
    } catch (err) {
      const code = err && err.name;
      if (code === "NotAllowedError" || code === "SecurityError") {
        showMicToast("Microphone blocked — allow access in your browser settings.");
      } else if (code === "NotFoundError") {
        showMicToast("No microphone found on this device.");
      } else {
        showMicToast("Microphone unavailable: " + (err.message || code || "unknown error"));
      }
      return;
    }

    rec = new SRCtor();
    rec.lang            = getLang() || "en-US";
    rec.continuous      = false;
    rec.interimResults  = true;
    rec.maxAlternatives = 1;
    const startValue = textarea.value;

    rec.onstart = () => {
      listening = true;
      btn.classList.add("recording");
      btn.setAttribute("aria-pressed", "true");
    };
    rec.onresult = (e) => {
      let interim = "", final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) final += r[0].transcript;
        else           interim += r[0].transcript;
      }
      const sep = startValue && !startValue.endsWith(" ") ? " " : "";
      textarea.value = startValue + sep + (final || interim);
      textarea.dispatchEvent(new Event("input"));
    };
    rec.onerror = (e) => {
      listening = false;
      btn.classList.remove("recording");
      btn.setAttribute("aria-pressed", "false");
      if (e && e.error === "not-allowed") {
        showMicToast("Microphone blocked — check your browser permissions.");
      } else if (e && e.error === "no-speech") {
        showMicToast("Didn't catch that — try again.");
      } else if (e && e.error === "audio-capture") {
        showMicToast("No microphone detected.");
      } else if (e && e.error === "network") {
        showMicToast("Speech service unreachable — voice input needs internet on Chrome.");
      }
    };
    rec.onend = () => {
      listening = false;
      btn.classList.remove("recording");
      btn.setAttribute("aria-pressed", "false");
    };
    try { rec.start(); }
    catch (err) {
      listening = false;
      btn.classList.remove("recording");
      showMicToast("Could not start recognition: " + err.message);
    }
  });
}

function sessionLang() {
  // Try to derive a BCP-47 tag from the case file's session language.
  const l = (blueprint.session && blueprint.session.language || "").toLowerCase();
  if (l.startsWith("en") || l.includes("english"))  return "en-US";
  if (l.startsWith("de") || l.includes("german") || l.includes("deutsch")) return "de-DE";
  if (l.startsWith("fr") || l.includes("french") || l.includes("français")) return "fr-FR";
  if (l.startsWith("es") || l.includes("spanish") || l.includes("español")) return "es-ES";
  return "en-US";
}

/* ---------- header + sidebar (case acts) ---------- */

function populateHeader() {
  const t = blueprint.teacher || {};
  const s = blueprint.session || {};
  document.title = "MindHeist — " + (t.name || "Session");
  dom.teacherName.textContent = t.name || "—";
  dom.teacherRole.textContent = (t.role || "—") + " · " + (s.language || "—");
}

function populateScenes() {
  dom.scenesList.innerHTML = "";
  (blueprint.phases || []).forEach((phase, i) => {
    const el = document.createElement("div");
    el.className = "scene" + (i === 0 ? " active" : "");
    el.dataset.phaseId = phase.id;
    el.innerHTML =
      '<div class="pico">' + (i + 1) + "</div>" +
      '<div class="title">' + escapeHtml(phase.name || ("Act " + (i + 1))) + "</div>";
    dom.scenesList.appendChild(el);
  });
}

function highlightPhase(phaseIndex) {
  const els = dom.scenesList.querySelectorAll(".scene");
  els.forEach((el, i) => el.classList.toggle("active", i === phaseIndex));
}

populateHeader();
populateScenes();
dom.composerInv.placeholder = "Respond to " + (blueprint.teacher?.name || "the narrator") + "…";

/* =========================================================================
   INVESTIGATION TAB
   ========================================================================= */

/**
 * Parse a teacher reply into ordered sections.
 * Returns: [{ type: "narration"|"npc"|"question"|"state", name?: string, content: string }, ...]
 * Strips the [STATE] block from the rendered output.
 */
function parseSections(text) {
  if (!text) return [];

  // Strip trailing [STATE] block from the rendered view (the backend already parses it).
  const stateIdx = text.search(/\[STATE\]/i);
  const visible = stateIdx >= 0 ? text.slice(0, stateIdx) : text;

  const tagRe = /\[(NARRATION|QUESTION|NPC:[^\]]+)\]/gi;
  const sections = [];
  let lastEnd = 0;
  let currentType = null;
  let currentName = null;

  const pushIfContent = (endIdx) => {
    if (currentType == null) return;
    const content = visible.slice(lastEnd, endIdx).trim();
    if (content) sections.push({ type: currentType, name: currentName, content });
  };

  let m;
  while ((m = tagRe.exec(visible)) !== null) {
    pushIfContent(m.index);
    const tag = m[1].toUpperCase();
    if (tag === "NARRATION") {
      currentType = "narration";
      currentName = null;
    } else if (tag === "QUESTION") {
      currentType = "question";
      currentName = null;
    } else if (tag.startsWith("NPC:")) {
      currentType = "npc";
      currentName = m[1].slice(4).trim();
    }
    lastEnd = tagRe.lastIndex;
  }
  pushIfContent(visible.length);

  // If the model returned no tags at all, surface the whole thing as one narration.
  if (sections.length === 0 && visible.trim()) {
    sections.push({ type: "narration", content: visible.trim() });
  }
  return sections;
}

function renderTeacherMessage(rawText) {
  const sections = parseSections(rawText);

  const msg = document.createElement("div");
  msg.className = "msg teacher";

  const av = document.createElement("div");
  av.className = "av";
  av.textContent = "GM";

  const body = document.createElement("div");
  body.className = "body";

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML =
    '<span class="name">' + escapeHtml(blueprint.teacher?.name || "Narrator") + "</span>" +
    '<span class="time">' + nowHHMM() + "</span>";
  body.appendChild(meta);

  const wrap = document.createElement("div");
  wrap.className = "teacher-response";

  for (const sec of sections) {
    if (sec.type === "narration") {
      const n = document.createElement("div");
      n.className = "narration";
      n.textContent = sec.content;
      wrap.appendChild(n);
    } else if (sec.type === "npc") {
      const block = document.createElement("div");
      block.className = "npc-block";
      const tag = document.createElement("div");
      tag.className = "npc-name-tag";
      tag.textContent = sec.name || "NPC";
      const bubble = document.createElement("div");
      bubble.className = "npc-bubble";
      bubble.textContent = sec.content;
      block.appendChild(tag);
      block.appendChild(bubble);
      wrap.appendChild(block);
    } else if (sec.type === "question") {
      const q = document.createElement("div");
      q.className = "practice-question";
      q.textContent = sec.content;
      wrap.appendChild(q);
    }
  }

  body.appendChild(wrap);
  msg.appendChild(av);
  msg.appendChild(body);
  dom.feedInv.appendChild(msg);
  scrollBottom(dom.transcriptInv);
  return msg;
}

function renderUserMessage(text) {
  const msg = document.createElement("div");
  msg.className = "msg user";

  const body = document.createElement("div");
  body.className = "body";

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML =
    '<span class="time">' + nowHHMM() + "</span>" +
    '<span class="name">Detective</span>';
  body.appendChild(meta);

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  body.appendChild(bubble);

  const av = document.createElement("div");
  av.className = "av";
  av.textContent = "D";

  msg.appendChild(body);
  msg.appendChild(av);
  dom.feedInv.appendChild(msg);
  scrollBottom(dom.transcriptInv);
  return msg;
}

function showTyping(feedEl) {
  const el = document.createElement("div");
  el.className = "msg teacher typing-msg";
  el.dataset.typing = "1";
  el.innerHTML =
    '<div class="av">GM</div>' +
    '<div class="body"><div class="typing"><span></span><span></span><span></span></div></div>';
  feedEl.appendChild(el);
  scrollBottom(feedEl.parentElement);
  return el;
}

function removeTyping(feedEl) {
  feedEl.querySelectorAll("[data-typing]").forEach((n) => n.remove());
}

function renderClosing(text) {
  const msg = document.createElement("div");
  msg.className = "msg teacher";
  msg.innerHTML =
    '<div class="av">GM</div>' +
    '<div class="body">' +
      '<div class="meta"><span class="name">' + escapeHtml(blueprint.teacher?.name || "Narrator") + '</span></div>' +
      '<div class="bubble bubble-closing">' + escapeHtml(text) + '</div>' +
      '<a class="btn-return" href="/">Return to library</a>' +
    "</div>";
  dom.feedInv.appendChild(msg);
  scrollBottom(dom.transcriptInv);
}

const investigationHistory = [];
let investigationClosed = false;

async function sendInvestigationMessage(text, { isHint = false } = {}) {
  text = text.trim();
  if (!text || investigationClosed) return;

  dom.composerInv.value = "";
  dom.composerInv.disabled = true;
  dom.sendInv.disabled = true;

  if (!isHint) renderUserMessage(text);

  const typingEl = showTyping(dom.feedInv);

  // history is the conversation up to (but not including) the current input;
  // the current input is passed separately as `message`.
  const historySnapshot = investigationHistory.slice();

  try {
    const res = await postWithRestore("/api/chat", {
      session_id: blueprint.session_id,
      message:    text,
      history:    historySnapshot,
    });
    if (!res.ok) {
      const errBody = await res.text().catch(() => "");
      throw new Error("HTTP " + res.status + (errBody ? (": " + errBody.slice(0, 200)) : ""));
    }
    const data = await res.json();
    typingEl.remove();

    renderTeacherMessage(data.reply || "");
    if (!isHint) investigationHistory.push({ role: "user", content: text });
    investigationHistory.push({ role: "assistant", content: data.reply || "" });

    if (typeof data.phase_index === "number") highlightPhase(data.phase_index);
    applyMoodFromResponse(data);

    if (data.closed) {
      investigationClosed = true;
      if (data.closing_line) renderClosing(data.closing_line);
      dom.composerInv.placeholder = "Investigation closed.";
    }
  } catch (err) {
    typingEl.remove();
    console.error(err);
    renderTeacherMessage(
      "[NARRATION] The line to the case file flickers for a moment, then steadies.\n\n" +
      "[NPC:Dispatch] \"Try again — we haven't lost the thread yet.\"\n\n" +
      "[QUESTION] What was your last thought before the connection dropped?"
    );
  } finally {
    if (!investigationClosed) {
      dom.composerInv.disabled = false;
      dom.sendInv.disabled = false;
      dom.composerInv.focus();
    }
  }
}

dom.sendInv.addEventListener("click", () => sendInvestigationMessage(dom.composerInv.value));
dom.composerInv.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendInvestigationMessage(dom.composerInv.value);
  }
});
dom.hintBtn?.addEventListener("click", () =>
  sendInvestigationMessage("[SYSTEM: hint requested]", { isHint: true })
);

/* Kick off the case: ask the server for the opening narration. */
(async function openCase() {
  const typingEl = showTyping(dom.feedInv);
  try {
    const res = await postWithRestore("/api/chat", {
      session_id: blueprint.session_id,
      message:    "[SYSTEM: begin the case]",
      history:    [],
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    typingEl.remove();
    renderTeacherMessage(data.reply || "");
    investigationHistory.push({ role: "assistant", content: data.reply || "" });
    if (typeof data.phase_index === "number") highlightPhase(data.phase_index);
    applyMoodFromResponse(data);
  } catch (err) {
    typingEl.remove();
    // Fall back to the blueprint's opening line if we can't reach the server.
    const opener = blueprint.opening?.first_line || "The file lies on the desk.";
    renderTeacherMessage(
      "[NARRATION] " + opener + "\n\n" +
      "[NPC:" + (blueprint.teacher?.name || "Narrator") + "] \"Let's begin.\"\n\n" +
      "[QUESTION] What stands out to you first?"
    );
  }
})();

/* =========================================================================
   INTERROGATION TAB
   ========================================================================= */

const interrogationState = {
  characters:       [],
  activeId:         null,
  historiesById:    {}, // character_id → [{role, content}]
  panelEls:         {}, // character_id → DOM container in feed
};

async function loadCharacters() {
  try {
    const res = await fetch("/api/session/" + encodeURIComponent(blueprint.session_id) + "/characters");
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    interrogationState.characters = data.characters || [];
  } catch (err) {
    // Fall back to the local blueprint snapshot.
    interrogationState.characters = (blueprint.characters || []).map((c) => ({
      id:          c.id || c.name,
      name:        c.name,
      role:        c.role,
      personality: c.personality,
    }));
  }
  renderCharacterList();
}

function renderCharacterList() {
  dom.charactersList.innerHTML = "";
  if (!interrogationState.characters.length) {
    const empty = document.createElement("div");
    empty.className = "character-empty";
    empty.textContent = "No characters in this case.";
    dom.charactersList.appendChild(empty);
    return;
  }
  for (const c of interrogationState.characters) {
    const item = document.createElement("button");
    item.className = "character" + (c.id === interrogationState.activeId ? " active" : "");
    item.dataset.characterId = c.id;
    item.innerHTML =
      '<div class="character-av">' + escapeHtml(initials(c.name)) + "</div>" +
      '<div class="character-text">' +
        '<div class="character-name">' + escapeHtml(c.name || "Unknown") + "</div>" +
        '<div class="character-role">' + escapeHtml(c.role || "—") + "</div>" +
      "</div>";
    item.addEventListener("click", () => selectCharacter(c.id));
    dom.charactersList.appendChild(item);
  }
}

function selectCharacter(id) {
  const c = interrogationState.characters.find((x) => x.id === id);
  if (!c) return;

  interrogationState.activeId = id;
  renderCharacterList();

  dom.interrogationEmpty?.classList.add("hidden");
  dom.interrogationName.textContent = c.name || "—";
  dom.interrogationRole.textContent = c.role || "—";
  dom.interrogationAv.textContent = initials(c.name);

  // Swap panel per character so each conversation is preserved.
  Array.from(dom.feedInter.children).forEach((el) => {
    if (el.classList.contains("interrogation-stream")) el.classList.add("hidden");
  });
  let panel = interrogationState.panelEls[id];
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "interrogation-stream";
    panel.dataset.characterId = id;
    interrogationState.panelEls[id] = panel;
    dom.feedInter.appendChild(panel);

    // Seed with a soft intro.
    const intro = document.createElement("div");
    intro.className = "interrogation-meta";
    intro.textContent = "You sit down across from " + (c.name || "the suspect") +
      ". They wait — guarded, not friendly. Ask your first question.";
    panel.appendChild(intro);
  } else {
    panel.classList.remove("hidden");
  }

  dom.composerInter.disabled = false;
  dom.composerInter.placeholder = "Ask " + (c.name || "them") + " a question…";
  dom.sendInter.disabled = false;
  dom.composerInter.focus();
  scrollBottom(dom.transcriptInter);
}

function appendInterrogationLine(panel, role, text) {
  const line = document.createElement("div");
  line.className = "interrogation-line " + (role === "user" ? "user" : "npc");

  const av = document.createElement("div");
  av.className = "interrogation-av";
  av.textContent = role === "user" ? "D" : initials(
    interrogationState.characters.find((c) => c.id === interrogationState.activeId)?.name || "?"
  );

  const bubble = document.createElement("div");
  bubble.className = "interrogation-bubble";
  bubble.textContent = text;

  if (role === "user") {
    line.appendChild(bubble);
    line.appendChild(av);
  } else {
    line.appendChild(av);
    line.appendChild(bubble);
  }
  panel.appendChild(line);
  scrollBottom(dom.transcriptInter);
  return line;
}

async function sendInterrogationMessage(text) {
  text = text.trim();
  const id = interrogationState.activeId;
  if (!text || !id) return;

  const panel = interrogationState.panelEls[id];
  if (!panel) return;

  dom.composerInter.value = "";
  dom.composerInter.disabled = true;
  dom.sendInter.disabled = true;

  appendInterrogationLine(panel, "user", text);

  const history = interrogationState.historiesById[id] || [];
  history.push({ role: "user", content: text });
  interrogationState.historiesById[id] = history;

  const typingLine = document.createElement("div");
  typingLine.className = "interrogation-line npc";
  typingLine.innerHTML =
    '<div class="interrogation-av">' + escapeHtml(initials(
      interrogationState.characters.find((c) => c.id === id)?.name || "?"
    )) + '</div>' +
    '<div class="typing"><span></span><span></span><span></span></div>';
  panel.appendChild(typingLine);
  scrollBottom(dom.transcriptInter);

  try {
    const res = await postWithRestore("/api/interrogate", {
      session_id:   blueprint.session_id,
      character_id: id,
      message:      text,
      history:      history.slice(0, -1), // history excludes the current message
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    typingLine.remove();
    appendInterrogationLine(panel, "npc", data.reply || "(silence)");
    history.push({ role: "assistant", content: data.reply || "" });
  } catch (err) {
    typingLine.remove();
    appendInterrogationLine(panel, "npc",
      "— they stay silent, looking past you —");
  } finally {
    dom.composerInter.disabled = false;
    dom.sendInter.disabled = false;
    dom.composerInter.focus();
  }
}

dom.sendInter.addEventListener("click", () => sendInterrogationMessage(dom.composerInter.value));
dom.composerInter.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendInterrogationMessage(dom.composerInter.value);
  }
});

/* =========================================================================
   TABS
   ========================================================================= */

function setTab(name) {
  const isInv = name === "investigation";
  dom.tabInvestigation.classList.toggle("on", isInv);
  dom.tabInterrogation.classList.toggle("on", !isInv);
  dom.tabInvestigation.setAttribute("aria-selected", String(isInv));
  dom.tabInterrogation.setAttribute("aria-selected", String(!isInv));
  // Use inline display alongside the .hidden class. Class-only toggling fought
  // .chat-panel { display: flex } from cached/older stylesheets and ended up
  // showing both panels stacked; inline style always wins.
  dom.panelInvestigation.style.display = isInv ? "flex" : "none";
  dom.panelInterrogation.style.display = isInv ? "none" : "flex";
  dom.sideActs.style.display           = isInv ? "flex" : "none";
  dom.sideCharacters.style.display     = isInv ? "none" : "flex";
  dom.panelInvestigation.classList.toggle("hidden", !isInv);
  dom.panelInterrogation.classList.toggle("hidden", isInv);
  dom.sideActs.classList.toggle("hidden", !isInv);
  dom.sideCharacters.classList.toggle("hidden", isInv);
  if (!isInv && !interrogationState.characters.length) {
    loadCharacters();
  }
}
// Apply the initial tab once, so the inline display values are coherent
// even if the cached HTML drifted from the current chat.js.
setTab("investigation");

dom.tabInvestigation.addEventListener("click", () => setTab("investigation"));
dom.tabInterrogation.addEventListener("click", () => setTab("interrogation"));

document.getElementById("end-btn")?.addEventListener("click", () => {
  if (confirm("End the session and return to the library?")) {
    sessionStorage.removeItem("mindheist_blueprint");
    moodAudio.setEnabled(false);
    window.location.href = "/";
  }
});

/* ---------- Mood audio + speech input wiring ---------- */

setupMic(dom.micInv,   dom.composerInv,   sessionLang);
setupMic(dom.micInter, dom.composerInter, sessionLang);

// Initial mood (before the first turn arrives)
moodAudio.setMood(MOOD_DEFAULT);

// First user gesture unlocks WebAudio (browser policy). Latch on any click
// inside the app — including the send button — so the drone starts naturally.
function unlockAudioOnce() {
  moodAudio.start();
  document.removeEventListener("pointerdown", unlockAudioOnce);
}
document.addEventListener("pointerdown", unlockAudioOnce);

// Music toggle
const updateMusicBtn = () => {
  if (!dom.musicBtn) return;
  dom.musicBtn.classList.toggle("muted", !moodAudio.enabled);
  dom.musicBtn.setAttribute("aria-pressed", String(!moodAudio.enabled));
};
dom.musicBtn?.addEventListener("click", () => {
  if (moodAudio.enabled) {
    moodAudio.setEnabled(false);
  } else {
    moodAudio.setEnabled(true);
    moodAudio.start();
  }
  updateMusicBtn();
});
updateMusicBtn();

// Pre-fetch characters so the tab swap is instant.
loadCharacters();
