"use strict";

const raw = sessionStorage.getItem("mindheist_blueprint");

if (!raw) {
  window.location.href = "/";
  throw new Error("No blueprint found");
}

const blueprint = JSON.parse(raw);

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;");
}

function nowHHMM() {
  const d = new Date();

  return (
    String(d.getHours()).padStart(2, "0") +
    ":" +
    String(d.getMinutes()).padStart(2, "0")
  );
}

function scrollBottom(el) {
  requestAnimationFrame(() => {
    el.scrollTo({
      top: el.scrollHeight,
      behavior: "smooth",
    });
  });
}

const feedEl = document.getElementById("feed");
const scenesList = document.getElementById("scenes-list");

function populateUI() {
  const teacher = blueprint.teacher;
  const session = blueprint.session;

  document.title = "MindHeist — " + teacher.name;

  document.getElementById("teacher-name").textContent =
    teacher.name;

  document.getElementById("teacher-role").textContent =
    `${teacher.role} · ${session.language}`;

  blueprint.phases.forEach((phase, i) => {
    const el = document.createElement("div");

    el.className = "scene" + (i === 0 ? " active" : "");

    el.dataset.phaseId = phase.id;

    el.innerHTML = `
      <div class="title">${escapeHtml(phase.name)}</div>
      <div class="num">${i + 1}</div>
    `;

    scenesList.appendChild(el);
  });

  document.getElementById("composer-input").placeholder =
    `Respond to ${teacher.name}...`;
}

populateUI();

function parseSections(text) {
  const stateIdx = text.search(/\[STATE\]/i);

  if (stateIdx !== -1) {
    text = text.slice(0, stateIdx);
  }

  text = text.trim();

  const parts = text.split(
    /(\[(?:NARRATION|NPC:[^\]]+|QUESTION)\])/i
  );

  const sections = [];

  let currentType = null;
  let currentName = null;

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];

    const match = part.match(
      /^\[(NARRATION|NPC:([^\]]+)|QUESTION)\]$/i
    );

    if (match) {
      const tag = match[1].toUpperCase();

      if (tag === "NARRATION") {
        currentType = "narration";
        currentName = null;
      }
      else if (tag === "QUESTION") {
        currentType = "question";
        currentName = null;
      }
      else {
        currentType = "npc";
        currentName = match[2]?.trim() || "NPC";
      }
    }
  }

  return sections;
}

function showTyping() {
  const el = document.createElement("div");

  el.className = "msg teacher";
  el.id = "typing-indicator";

  el.innerHTML = `
    <div class="av">AI</div>

    <div class="body">
      <div class="bubble">Typing...</div>
    </div>
  `;

  feedEl.appendChild(el);

  scrollBottom(feedEl);
}

function hideTyping() {
  const el = document.getElementById("typing-indicator");

  if (el) {
    el.remove();
  }
}

const composer = document.getElementById("composer-input");
const sendBtn = document.getElementById("send-btn");

let history = [];

async function sendMessage() {
  const text = composer.value.trim();

  if (!text) {
    return;
  }

  composer.value = "";

  addUserMessage(text);

  history.push({
    role: "user",
    content: text,
  });

  showTyping();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        session_id: blueprint.session_id,
        message: text,
        history,
      }),
    });

    if (!response.ok) {
      throw new Error("Chat request failed");
    }

    const data = await response.text();

    hideTyping();

    addTeacherMessage(data);

    history.push({
      role: "assistant",
      content: data,
    });
  }
  catch (err) {
    console.error(err);

    hideTyping();

    addTeacherMessage(
      "[NARRATION] The connection to the investigation breaks for a moment.\n\n[QUESTION] Try again?\n\n[STATE] STAY"
    );
  }
}

sendBtn.addEventListener("click", sendMessage);

composer.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

addTeacherMessage(
  "[NARRATION] The case file slides onto the desk under a cold overhead light. A name has been crossed out twice in black ink. The investigation begins immediately.\n\n[NPC:Dispatcher] \"The department wants answers before sunrise. Start with the evidence board.\"\n\n[QUESTION] What is the first conclusion you draw from the opening evidence?\n\n[STATE] STAY"
);