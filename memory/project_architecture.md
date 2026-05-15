---
name: project-architecture
description: MindHeist project — FastAPI+Ollama backend, vanilla JS frontend, noir detective learning game for Gemma4 hackathon
metadata:
  type: project
---

# MindHeist — Project Architecture

FastAPI + Ollama (gemma4 model) backend, vanilla JS frontend, no build step.
Static files served by FastAPI's StaticFiles.

## Source Files
- `main.py` — FastAPI app, blueprint dataclasses, Ollama wrappers, all API endpoints
- `setup_prompt.txt` — system prompt for blueprint generation (LLM architect)
- `task_design_prompt.txt` — Stage 2 exam-task design prompt (now with humanities guidance)
- `research_prompt.txt` — Stage 1 curriculum-analyst prompt (now with per-domain notes)
- `teacher_system_prompt.txt` — system prompt for in-session teacher agent
- `teacher_user_prompt.txt` — user turn template for teacher agent (format placeholders)
- `interrogation_system_prompt.txt` — system prompt for character interrogation
- `chat.html` / `chat.js` / `chat.css` — session UI (Investigation + Interrogation tabs)
- `index.html` / `script.js` / `style.css` — landing page / lesson setup form
- `shared.css` — CSS variables and shared layout
- `REASONING_PROCESS.md` — author reasoning for the two worked example cases
  (Photosynthese murder + Gedichtsanalyse murder) used to anchor the prompts
- `tests_e2e.py` / `tests_frontend.mjs` / `tests_integration.py` — local smoke tests
  (mock Ollama; verify endpoints, parser, UI hooks, and full chat flow)

## API endpoints
- `POST /api/work` and `POST /api/work/stream` — three-stage blueprint generation
- `POST /api/chat` and `POST /api/chat/stream` — turn-based game-master conversation
- `GET  /api/session/{session_id}/characters` — NPC roster for the active session
- `POST /api/interrogate` — direct dialogue with one named character (uses
  `interrogation_system_prompt.txt`; replies are plain prose, section tags stripped)

## Token budgets (main.py, _OPTS_*)
Bumped so that blueprints and the early stages cannot be truncated:
  Research: 2048 · Task design: 8192 · Blueprint: 12288 · Validation: 1536
  Chat: 2048 · Interrogation: 768

## Chat UI
- Two tabs in `chat.html`:
    * Investigation — main game-master flow, sidebar shows case acts
    * Interrogation — picker of all NPCs in the sidebar, per-character history kept
- `parseSections()` now actually returns the parsed sections (`narration`, `npc`, `question`);
  previous version returned [] every time and broke rendering.
- `renderUserMessage` / `renderTeacherMessage` (no longer undefined `addUserMessage` /
  `addTeacherMessage`). Response parsed as JSON (was wrongly read as text).
- Opener: `/api/chat` is called with `[SYSTEM: begin the case]`, which is treated as a hint
  (no turn counted) so the server emits the opening narration without consuming a move.

## Key Concepts
- **SessionBlueprint** — fully-structured case dataclass; generated once per session by `build_story()`
- **Moves** — story beats with routing (if_correct/if_incorrect), hint, and now:
  - `source_ref` — curriculum citation (never shown to student, validation only)
  - `is_error_trap` — move contains a deliberate wrong fact the student must correct
  - `error_correction_key` — the correct value for error trap moves
- **Phases** — arc stages (Setup → Investigation → Complication → Breakthrough → Confrontation)
- **MoodEngine** — CSS variable system; 5 moods (neutral, warm, tense, calm, danger)
- **MusicEngine** — Web Audio API procedural ambient piano; phase-driven; classroom-safe (max gain 0.08); default muted

## Teacher Agent Dynamic Difficulty
- `accuracy_ratio = correct_count / turn_count` computed per request
- Passed to `_build_teacher_prompts` → `teacher_user_prompt.txt` as `{accuracy_note}`
- Three tiers: HIGH (≥80%, 3+ moves) → more complexity; LOW (≤25%, 3+ moves) → more scaffolding; BALANCED → maintain
- `accuracy_ratio` also returned in streaming done event to frontend

## Blueprint Generation Rules (setup_prompt.txt)
- CHECK 1–5: existing content, term, routing, first-line, and character checks
- **CHECK 6** — CAUSAL CHAIN: each move's answer must be unlocked by the prior move's content
- **CHECK 7** — ERROR TRAP: ≥1 move with is_error_trap=true required per blueprint
- New design rules: NO REAL PERSONS/PLACES; EMBED ERROR TRAP; CAUSAL PREREQUISITE CHAIN; SOURCE REFERENCES MANDATORY

## Why: Hackathon requirement
Making facts causally load-bearing (not ambient), embedding correctable errors, and dynamic difficulty adjustment to improve pedagogical integrity for the Gemma4 contest submission.
