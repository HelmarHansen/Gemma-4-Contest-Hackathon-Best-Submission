# MindHeist — Exam Prep as a Noir Detective Game

**MindHeist** turns any exam topic into an immersive noir detective investigation powered by [Gemma 4](https://ai.google.dev/gemma) running locally via Ollama. A crime is constructed around your study material — suspects hold the facts, clues encode the theory. You crack the case by demonstrating what you know.

> Built for the [Gemma 4 Hackathon](https://kaggle.com/competitions/gemma-3-hackathon).

---

## How it works

1. **You describe the case** — paste a topic, pick an investigation style (Cold Case / Murder / Conspiracy / Heist), set difficulty and length.
2. **The engine researches the topic** — Gemma 4 produces a structured brief of core concepts, key facts, and common misconceptions.
3. **A full session blueprint is generated** — a noir narrative with scenes, NPCs, clues, branching dialogue moves, and contingency plans, all grounded in your material.
4. **You play the detective** — a chat interface lets you interrogate witnesses, examine clues, and advance the case. You only progress when your answers are factually correct.

The story adapts in real time: wrong answers redirect to remediation moves, correct answers unlock the next scene. The session closes with a performance-aware line (success / partial / fail).

---

## Architecture

```
main.py          FastAPI backend — three LLM passes + session management
setup_prompt.txt System prompt for blueprint generation (the "case architect")
teacher_system_prompt.txt  System prompt for the in-session teacher/narrator agent
teacher_user_prompt.txt    User-turn template for the teacher agent
index.html       Setup UI (material upload, narrator config, case settings)
chat.html        Chat UI (in-session detective interface)
style.css / script.js      Setup page styles and logic
chat.css / chat.js         Chat page styles and logic
```

### Three-pass LLM pipeline

| Pass | Model options | Purpose |
|------|--------------|---------|
| Research | `_OPTS_RESEARCH` (temp 0.15) | Topic brief — core concepts, key facts, misconceptions |
| Blueprint | `_OPTS_BLUEPRINT` (temp 0.25, up to 10k tokens) | Full `SessionBlueprint` JSON |
| Validation | `_OPTS_VALIDATE` (temp 0.10) | Fact-checks every expected student answer; flags errors |

During chat, a fourth call (`_OPTS_CHAT`, temp 0.35) drives the teacher agent, which returns a reply plus a `[STATE]` signal (`ADVANCE` / `STAY` / `CLOSE`) that controls branching.

### SessionBlueprint

The blueprint is a strongly-typed dataclass tree (`SessionBlueprint`) serialised as JSON and stored in memory per session. It contains:

- **Teacher** — narrator persona, voice, signature phrases
- **Session** — mode, language, difficulty, pacing, hint policy
- **Topic** — learning goals, weak spots, material summary
- **Arc** — ordered phases (Setup → Investigation → Complication → Breakthrough → Resolution)
- **Moves** — branching story beats with `if_correct` / `if_incorrect` routing
- **Contingencies** — off-topic, silent student, consistently wrong, etc.
- **Opening / Closing** — first line and three performance-dependent endings
- **Execution rules** — how the teacher picks moves, response length, hard constraints

---

## Setup

### Requirements

- Python 3.12+
- [Ollama](https://ollama.com) with `gemma4` pulled

```bash
ollama pull gemma4
```

### Install & run

```bash
pip install fastapi uvicorn requests pydantic
uvicorn main:app --reload
```

Open `http://localhost:8000` in your browser.

---

## Usage

1. **Material (optional)** — drop a PDF, DOCX, TXT, or image. The text is extracted and passed to the blueprint generator as additional source material.
2. **Narrator** — give your narrator a name, role, and personality. Hit "Surprise me" for a random preset.
3. **The case** — describe your exam topic in plain text. Choose an investigation style, language, session length, school type / grade, and academic difficulty.
4. **Open the case** — the three-pass pipeline runs (≈30–90 s depending on hardware). You are redirected to the chat interface when ready.
5. **Play** — type your answers as the detective. A progress bar shows your current phase. Use the hint button if you're stuck.

---

## Difficulty levels

| Range | Label | Expected age |
|-------|-------|-------------|
| 0.0–0.3 | Forgiving | Klasse 5–7 |
| 0.4–0.6 | Balanced | Klasse 8–10 |
| 0.7–0.85 | Challenging | Oberstufe / Abitur |
| 0.86–1.0 | No mercy | University |

---

## Investigation styles

| Style | Mood | Structure |
|-------|------|-----------|
| **Cold Case** | Melancholy, archival | Sparse evidence, reconstructed timeline |
| **Murder** | Urgent, tense | Fresh scene, alibi testing, interrogation |
| **Conspiracy** | Paranoid, layered | Web of actors, find the connecting thread |
| **Heist** | Cerebral, procedural | Trace the method, path, and culprit |

---

## License

MIT — see [LICENSE](LICENSE).
