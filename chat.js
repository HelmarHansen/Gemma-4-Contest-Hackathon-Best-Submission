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
const blueprint = JSON.parse(raw);

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
  // interrogation
  feedInter:          document.getElementById("feed-interrogation"),
  transcriptInter:    document.getElementById("transcript-interrogation"),
  composerInter:      document.getElementById("composer-interrogation"),
  sendInter:          document.getElementById("send-interrogation"),
  interrogationEmpty: document.getElementById("interrogation-empty"),
  interrogationName:  document.getElementById("interrogation-name"),
  interrogationRole:  document.getElementById("interrogation-role"),
  interrogationAv:    document.getElementById("interrogation-avatar"),
};

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
      '<div class="title">' + escapeHtml(phase.name || ("Act " + (i + 1))) + "</div>" +
      '<div class="num">' + (i + 1) + "</div>";
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
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: blueprint.session_id,
        message:    text,
        history:    historySnapshot,
      }),
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

    if (data.closed) {
      investigationClosed = true;
      if (data.closing_line) renderClosing(data.closing_line);
      dom.composerInv.placeholder = "Investigation closed.";
    }
  } catch (err) {
    typingEl.remove();
    console.error(err);
    renderTeacherMessage(
      "[NARRATION] Die Verbindung zur Akte reißt für einen Moment ab.\n\n" +
      "[NPC:Dispatch] „Versuch es nochmal — wir haben den Faden noch nicht verloren.\"\n\n" +
      "[QUESTION] Was war dein letzter Gedanke, bevor die Leitung abriss?"
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
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: blueprint.session_id,
        message:    "[SYSTEM: begin the case]",
        history:    [],
      }),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    typingEl.remove();
    renderTeacherMessage(data.reply || "");
    investigationHistory.push({ role: "assistant", content: data.reply || "" });
    if (typeof data.phase_index === "number") highlightPhase(data.phase_index);
  } catch (err) {
    typingEl.remove();
    // Fall back to the blueprint's opening line if we can't reach the server.
    const opener = blueprint.opening?.first_line || "Die Akte liegt auf dem Tisch.";
    renderTeacherMessage(
      "[NARRATION] " + opener + "\n\n" +
      "[NPC:" + (blueprint.teacher?.name || "Narrator") + "] „Wir fangen an.\"\n\n" +
      "[QUESTION] Was fällt Ihnen als Erstes auf?"
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
    const res = await fetch("/api/interrogate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id:   blueprint.session_id,
        character_id: id,
        message:      text,
        history:      history.slice(0, -1), // history excludes the current message
      }),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    typingLine.remove();
    appendInterrogationLine(panel, "npc", data.reply || "(silence)");
    history.push({ role: "assistant", content: data.reply || "" });
  } catch (err) {
    typingLine.remove();
    appendInterrogationLine(panel, "npc",
      "— die Person bleibt still und sieht durch dich hindurch —");
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
  dom.panelInvestigation.classList.toggle("hidden", !isInv);
  dom.panelInterrogation.classList.toggle("hidden", isInv);
  dom.sideActs.classList.toggle("hidden", !isInv);
  dom.sideCharacters.classList.toggle("hidden", isInv);
  if (!isInv && !interrogationState.characters.length) {
    loadCharacters();
  }
}

dom.tabInvestigation.addEventListener("click", () => setTab("investigation"));
dom.tabInterrogation.addEventListener("click", () => setTab("interrogation"));

// Pre-fetch characters so the tab swap is instant.
loadCharacters();
