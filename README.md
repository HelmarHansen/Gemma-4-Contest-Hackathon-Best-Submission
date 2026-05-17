# MindHeist — Exam Prep as a Noir Detective Game

**MindHeist** turns any exam topic into an immersive noir detective investigation,
powered by **Gemma 4** running locally through **Ollama**. The system builds a crime
around your study material — suspects hold the facts, clues encode the theory.
You crack the case by demonstrating what you know.

> Built for the [Gemma 4 Hackathon](https://kaggle.com/competitions/gemma-3-hackathon).

![status](https://img.shields.io/badge/runs-100%25%20local-2e7d32)
![model](https://img.shields.io/badge/model-gemma4%208B-1f6feb)
![ui](https://img.shields.io/badge/UI-vanilla%20JS-555)

---

## What you get

- **Local, private, on-device** — every LLM call is routed to Ollama on `localhost`;
  no API keys, no telemetry, no internet round-trip for inference.
- **Study material → case file** — drop a PDF, DOCX, PPTX, XLSX or paste plain text.
  The backend extracts the content (text + rendered page images for PDFs) and the
  blueprint stage builds the mystery directly from your material.
- **Four detective formats, auto-selected** — Cold Case, Murder, Conspiracy, Heist.
  The mode is chosen automatically from your topic and material; you just describe
  what you want to study.
- **Adaptive narrative branching** — correct answers move the case forward;
  vague or wrong answers stay on the same concept with a fresh angle.
  Branching is driven by an explicit `[STATE]` signal the model emits each turn.
- **Mood-driven ambient soundtrack** — a procedural Web-Audio score (bass drone,
  chord pad, vinyl crackle, sparse melodic punctuation) crossfades between
  `calm / neutral / warm / tense / danger` according to the phase and mode.
- **Voice input** — click the microphone to dictate. Uses the Web Speech API and
  asks for explicit microphone permission, with clear error messages if it's
  blocked.
- **In-character interrogations** — second tab lets you question any suspect
  one-on-one; they answer only with what their character knowledge allows
  (no game-master narration).

---

## How it works

1. **You describe the case.** Topic, optional material, narrator persona,
   difficulty, language.
2. **Three-stage LLM pipeline.**
   - *Research* — Gemma extracts core concepts, key facts, common misconceptions.
   - *Task design* — concrete exam tasks are designed from the research brief,
     each tied to a story hook.
   - *Blueprint* — a complete `SessionBlueprint` JSON is generated: arc, phases,
     branching moves, characters, contingencies, opening/closing lines.
3. **You play the detective.** Every turn the teacher agent returns four blocks
   (`[NARRATION]`, `[NPC:Name]`, `[QUESTION]`, `[STATE]`) plus a mood tag the
   frontend uses to retint the page and steer the soundtrack.
4. **The closing line is performance-aware** — success / partial / fail depending
   on your hit rate over the session.

---

## Architecture

```
main.py                   FastAPI backend, 3-stage pipeline + session state
research_prompt.txt       Stage 1 — curriculum analyst
task_design_prompt.txt    Stage 2 — exam task author
setup_prompt.txt          Stage 3 — case architect (the SessionBlueprint)
teacher_system_prompt.txt Live teacher / narrator persona
teacher_user_prompt.txt   Per-turn user template (active move + history + roster)
interrogation_system_prompt.txt  Per-character interrogation persona

index.html  /  style.css  /  script.js      Case-setup page
chat.html   /  chat.css   /  chat.js        In-session UI
shared.css                                  Common styles
```

### LLM passes

| Pass            | Options                              | Purpose                                       |
|-----------------|--------------------------------------|-----------------------------------------------|
| Research        | `_OPTS_RESEARCH`  (temp 0.15)        | Core concepts, key facts, misconceptions      |
| Task design     | `_OPTS_TASK_DESIGN` (temp 0.25)      | Concrete tasks per concept, with story hooks  |
| Blueprint       | `_OPTS_BLUEPRINT` (temp 0.25)        | Full `SessionBlueprint` JSON                  |
| Validation      | `_OPTS_VALIDATE` (temp 0.10)         | Fact-checks every expected student answer     |
| Chat turn       | `_OPTS_CHAT`     (temp 0.30)         | Teacher reply + `[STATE]` routing signal      |
| Interrogation   | `_OPTS_INTERROGATE` (temp 0.45)      | One NPC voice, knowledge-bounded              |

### Post-processing safeguards (in `main.py`)

A small 8B model can drift on long-form structured output, so each chat reply
is passed through three light cleanups:

- `_strip_duplicate_response` — collapses occasional verbatim doubles.
- `_strip_prompt_leaks` — removes warning lines that sometimes leak from the
  system prompt into the model's output.
- `_strip_teacher_from_characters` — guards against the blueprint adding the
  teacher to the `characters[]` array (which would let the narrator speak as
  an NPC). Applied at generation **and** restore time.
- `_infer_state_from_answer` — if the model forgets to emit `ADVANCE` / `STAY`
  after `[STATE]`, a simple heuristic on the student answer (length + keyword
  overlap with the move's expected answer) fills it in.

---

## Requirements

- Python **3.10+**
- [Ollama](https://ollama.com) installed and running
- Disk space for the Gemma 4 model (~9 GB for `gemma4:latest`, 8B Q4_K_M)

### Install Ollama + the model

```bash
ollama pull gemma4
ollama serve   # if not already running as a service
```

### Python dependencies

```bash
pip install fastapi uvicorn requests pydantic \
            pymupdf python-docx python-pptx openpyxl
```

(The four document libraries are only needed if you plan to upload PDFs,
DOCX, PPTX or XLSX files. Plain text always works.)

### Run

```bash
uvicorn main:app --reload
```

Then open <http://localhost:8000> in Chrome, Edge, or Safari.

---

## Usage

1. **Narrator** — give the narrator a name, role, personality, and optional traits.
2. **Material** — drop a PDF / DOCX / PPTX / XLSX, or just describe the topic
   in your own words. Both work.
3. **The case** — describe what you want to be examined on. The mystery format
   (Cold Case / Murder / Conspiracy / Heist) is **picked automatically** from
   your topic and material.
4. **Open the case** — the three-stage pipeline runs (~60–120 s on an M-series
   Mac with `gemma4:latest`). You're redirected to the chat once ready.
5. **Play** — type or dictate your answers. Use the hint button when stuck;
   switch to *Interrogation* to pressure a single suspect.

---

## Difficulty calibration

| Range     | Label        | Expected level                  |
|-----------|--------------|---------------------------------|
| 0.0–0.3   | Forgiving    | Elementary / Middle school      |
| 0.4–0.6   | Balanced     | Late middle / Early high school |
| 0.7–0.85  | Challenging  | Upper high school / Abitur      |
| 0.86–1.0  | No mercy     | University / Graduate           |

The teacher prompt also reads a live accuracy ratio and tightens or scaffolds
in response, so the curve self-tunes mid-session.

---

## Detective formats (auto-selected)

| Format         | Mood profile                  | Story core                                       |
|----------------|-------------------------------|--------------------------------------------------|
| **Cold Case**  | Archival, melancholic         | Aged file, fragmentary traces, reconstruction    |
| **Murder**     | Urgent, tense                 | Fresh body, named cause, testable alibis         |
| **Conspiracy** | Paranoid, layered             | ≥3 nodes linked by a hidden pattern              |
| **Heist**      | Cerebral, procedural          | Stolen object, scene, time window, logs/sensors  |

Mode selection is a simple keyword pass over topic + material; if nothing
matches, the system picks deterministically from a hash of the input so
different sessions feel different.

---

## Audio & speech

- The chat UI requests a microphone permission on first click, then uses
  `webkit/SpeechRecognition` in the session language.
- The ambient soundtrack uses **only Web Audio nodes** — bass drone (sine + saw
  through a low-pass), chord pad with chorus LFOs, pink-noise vinyl crackle,
  and occasional triangle "pings" in tense / danger moods. No external files
  ship with the app, so it works fully offline.
- Both the music and the voice input can be toggled from the top bar.

---

## Layout in your repo

```
.
├── main.py                    # FastAPI + 3-stage Gemma pipeline
├── *.txt                      # All prompts (research / tasks / blueprint / teacher / interrogation)
├── index.html / style.css     # Case-setup page
├── script.js                  # Setup-page logic + SSE consumer for blueprint streaming
├── chat.html / chat.css       # In-session page
├── chat.js                    # Chat logic + mood audio + speech input + interrogation
├── shared.css                 # Variables and reset shared by both pages
├── tests_e2e.py               # End-to-end test (requires Ollama)
├── tests_integration.py       # API integration tests
└── README.md
```

---

## Hackathon constraints

- **All inference local** — `OLLAMA_URL = "http://localhost:11434/api/chat"`,
  `MODEL = "gemma4"`. No external API call paths exist in the code.
- **Single binary deps for build** — `pip install` only; no compiled binaries
  outside Ollama itself.
- **Single-file backend** — `main.py` is intentionally one file for the
  submission to be easy to read and audit.

---

## License

MIT — see [LICENSE](LICENSE).
