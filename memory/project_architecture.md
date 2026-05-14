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
- `teacher_system_prompt.txt` — system prompt for in-session teacher agent
- `teacher_user_prompt.txt` — user turn template for teacher agent (format placeholders)
- `interrogation_system_prompt.txt` — system prompt for character interrogation
- `chat.html` / `chat.js` / `chat.css` — session UI (investigation + interrogation tabs)
- `index.html` / `script.js` / `style.css` — landing page / lesson setup form
- `shared.css` — CSS variables and shared layout

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
