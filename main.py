import json
import re
import dataclasses
import requests
from dataclasses import dataclass, field, asdict
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "gemma4"

# ── Ollama parameter presets ─────────────────────────────────────
_OPTS_RESEARCH  = {"temperature": 0.15, "top_p": 0.85, "top_k": 30,
                   "repeat_penalty": 1.05, "num_predict": 1024}
_OPTS_BLUEPRINT = {"temperature": 0.25, "top_p": 0.85, "top_k": 40,
                   "repeat_penalty": 1.10, "num_predict": 12000}
_OPTS_VALIDATE  = {"temperature": 0.10, "top_p": 0.80, "top_k": 20,
                   "repeat_penalty": 1.00, "num_predict": 512}
_OPTS_CHAT      = {"temperature": 0.30, "top_p": 0.88, "top_k": 45,
                   "repeat_penalty": 1.20, "num_predict": 1500}

# ── Blueprint dataclasses ────────────────────────────────────────

@dataclass
class Character:
    id:               str = ""
    name:             str = ""
    role:             str = ""
    personality:      str = ""
    voice:            str = ""
    knowledge:        str = ""
    secrets:          str = ""
    ignorant_of:      str = ""
    appears_in_moves: list[str] = field(default_factory=list)

@dataclass
class Teacher:
    name:                 str = ""
    role:                 str = ""
    voice:                str = ""
    active_traits:        list[str] = field(default_factory=list)
    expects_from_student: str = ""
    will_not_do:          str = ""
    signature_phrases:    list[str] = field(default_factory=list)

@dataclass
class Session:
    mode:            str   = ""
    language:        str   = "English"
    immersive:       bool  = True
    difficulty:      float = 0.5
    pacing:          str   = "steady"
    estimated_turns: int   = 25
    hint_policy:     str   = "only if asked"

@dataclass
class Topic:
    raw:               str = ""
    core_subject:      str = ""
    learning_goals:    list[str] = field(default_factory=list)
    likely_weak_spots: list[str] = field(default_factory=list)
    out_of_scope:      str = ""
    material_summary:  str = ""

@dataclass
class Phase:
    id:               str = ""
    name:             str = ""
    goal:             str = ""
    turn_budget:      int = 5
    teacher_strategy: str = ""
    exit_condition:   str = ""
    fallback:         str = ""

@dataclass
class Move:
    id:                        str = ""
    phase:                     str = ""
    type:                      str = "scene"
    trigger:                   str = ""
    content:                   str = ""
    expected_student_response: str = ""
    if_correct:                str = ""
    if_incorrect:              str = ""
    hint:                      str | None = None

@dataclass
class Contingencies:
    student_goes_off_topic:        str = ""
    student_asks_for_answer:       str = ""
    student_is_silent:             str = ""
    student_is_consistently_wrong: str = ""
    student_finishes_early:        str = ""

@dataclass
class Opening:
    first_line:      str = ""
    opening_move_id: str = ""

@dataclass
class Closing:
    success_line: str = ""
    partial_line: str = ""
    fail_line:    str = ""

@dataclass
class ExecutionRules:
    how_to_pick_next_move:       str = ""
    when_to_deviate_from_plan:   str = ""
    response_length_guideline:   str = ""
    never_do:                    list[str] = field(default_factory=list)

@dataclass
class SessionBlueprint:
    session_id:      str
    teacher:         Teacher
    session:         Session
    topic:           Topic
    phases:          list[Phase]
    moves:           list[Move]
    characters:      list[Character]
    contingencies:   Contingencies
    opening:         Opening
    closing:         Closing
    execution_rules: ExecutionRules
    _move_index: dict[str, Move]      = field(default_factory=dict, repr=False)
    _char_index: dict[str, Character] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._move_index = {m.id: m for m in self.moves}
        self._char_index = {c.id: c for c in self.characters}

    def get_move(self, move_id: str) -> Move | None:
        return self._move_index.get(move_id)

    def get_character(self, char_id: str) -> Character | None:
        return self._char_index.get(char_id)

    def get_opening_move(self) -> Move | None:
        return self.get_move(self.opening.opening_move_id)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_move_index", None)
        d.pop("_char_index", None)
        return d

    @classmethod
    def from_llm_response(cls, raw: str) -> "SessionBlueprint":
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in model response")
        json_str = match.group()
        json_str = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", json_str)
        json_str = re.sub(
            r'"((?:[^"\\]|\\.)*)"',
            lambda m: '"' + m.group(1).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') + '"',
            json_str,
        )
        depth = 0
        last_close = -1
        for i, ch in enumerate(json_str):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_close = i
                    break
        if last_close != -1:
            json_str = json_str[: last_close + 1]
        data = json.loads(json_str)

        def fit(cls_, d: dict):
            # Strip unknown keys so new blueprint fields don't break old dataclasses
            if not isinstance(d, dict):
                return cls_()
            keys = {f.name for f in dataclasses.fields(cls_)}
            return cls_(**{k: v for k, v in d.items() if k in keys})

        def get(key, default=None):
            return data.get(key) or default

        return cls(
            session_id=get("session_id", "session"),
            teacher=fit(Teacher, get("teacher", {})),
            session=fit(Session, get("session", {})),
            topic=fit(Topic, get("topic", {})),
            phases=[fit(Phase, p) for p in get("arc", {}).get("phases", [])],
            moves=[fit(Move, m) for m in get("planned_moves", [])],
            characters=[fit(Character, c) for c in get("characters", [])],
            contingencies=fit(Contingencies, get("contingencies", {})),
            opening=fit(Opening, get("opening", {})),
            closing=fit(Closing, get("closing", {})),
            execution_rules=fit(ExecutionRules, get("execution_rules", {})),
        )

# ── Request schema ───────────────────────────────────────────────

class TeacherInput(BaseModel):
    name:        str
    role:        str
    personality: str
    traits:      list[str]

class LessonInput(BaseModel):
    topic:       str
    mode:        str
    language:    str
    length:      str
    difficulty:  float
    school_type: str = ""
    grade:       str = ""

class WorkRequest(BaseModel):
    teacher:  TeacherInput
    lesson:   LessonInput
    material: str = ""

class ChatMessage(BaseModel):
    role:    str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    message:    str
    history:    list[ChatMessage] = []

class InterrogateRequest(BaseModel):
    session_id:   str
    character_id: str
    message:      str
    history:      list[ChatMessage] = []

class DebugGotoRequest(BaseModel):
    move_id: str

# ── Ollama helpers ───────────────────────────────────────────────

def ask_ollama(system_prompt: str, user_message: str,
               options: dict | None = None) -> str:
    payload: dict = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "stream": False,
    }
    if options:
        payload["options"] = options
    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["message"]["content"]

def ask_ollama_stream(system_prompt: str, user_message: str,
                      options: dict | None = None):
    # Sync generator: FastAPI wraps it in a thread via StreamingResponse,
    # so we can use blocking requests.post here without async complexity.
    payload: dict = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "stream": True,
    }
    if options:
        payload["options"] = options
    with requests.post(OLLAMA_URL, json=payload, stream=True, timeout=300) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break

def _load_prompt(filename: str) -> str:
    with open(filename, "r", encoding="utf-8") as f:
        return f.read()

# ── Prompt building ──────────────────────────────────────────────

def _build_teacher_prompts(
    blueprint:        "SessionBlueprint",
    user_prompt:      str,
    current_move:     "Move | None",
    history:          list["ChatMessage"] | None = None,
    visited_move_ids: list[str] | None = None,
) -> tuple[str, str]:
    """Returns (system_prompt, user_message) for the teacher agent."""
    system_template = _load_prompt("teacher_system_prompt.txt")
    system_prompt = system_template.format(
        teacher_name=blueprint.teacher.name,
        teacher_role=blueprint.teacher.role,
        teacher_voice=blueprint.teacher.voice,
        teacher_traits=json.dumps(blueprint.teacher.active_traits, ensure_ascii=False),
        teacher_phrases=json.dumps(blueprint.teacher.signature_phrases, ensure_ascii=False),
        will_not_do=blueprint.teacher.will_not_do,
    )

    blueprint_json = json.dumps(blueprint.to_dict(), ensure_ascii=False, indent=2)

    history_text = "(none)"
    if history:
        lines = []
        for msg in history:
            label = "DETECTIVE" if msg.role == "user" else "GAME MASTER"
            lines.append(f"{label}: {msg.content}")
        history_text = "\n".join(lines)

    current_move_json = json.dumps(
        dataclasses.asdict(current_move) if current_move else {},
        ensure_ascii=False, indent=2,
    )
    is_closing_move = current_move and current_move.type == "closing"

    visited_ids = visited_move_ids or []
    already_tested_lines = []
    for mid in visited_ids:
        m = blueprint.get_move(mid)
        if m and m.id != (current_move.id if current_move else None):
            already_tested_lines.append(f"- [{m.id}] {m.expected_student_response}")
    already_tested = "\n".join(already_tested_lines) if already_tested_lines else "(none yet)"

    user_template = _load_prompt("teacher_user_prompt.txt")
    user_message = user_template.format(
        blueprint_json=blueprint_json,
        history=history_text,
        user_prompt=user_prompt,
        current_move_json=current_move_json,
        is_closing_move="YES — this is the final move. Use CLOSE if the student answers correctly."
                        if is_closing_move else "NO",
        already_tested=already_tested,
    )
    return system_prompt, user_message

def run_teacher_agent(
    blueprint:        "SessionBlueprint",
    user_prompt:      str,
    current_move:     "Move | None",
    history:          list["ChatMessage"] | None = None,
    visited_move_ids: list[str] | None = None,
) -> tuple[str, str]:
    """Returns (clean_reply_without_STATE, state_signal)."""
    system_prompt, user_message = _build_teacher_prompts(
        blueprint, user_prompt, current_move, history, visited_move_ids,
    )
    raw = ask_ollama(system_prompt, user_message, options=_OPTS_CHAT)

    state = "STAY"
    state_match = re.search(
        r"\[STATE\][:\s]*\n?\s*(ADVANCE|STAY|CLOSE)", raw, re.IGNORECASE
    )
    if state_match:
        state = state_match.group(1).upper()
        raw = raw[:state_match.start()].rstrip()

    return raw, state

# ── Research & validation system prompts ────────────────────────

_RESEARCH_SYSTEM = """\
You are a curriculum expert and subject-matter specialist. Given a topic, school level, and grade,
produce a structured research brief that will be used to build an exam-prep detective scenario.

Output plain text with these four sections — no JSON, no markdown headers:

CORE CONCEPTS: List the 6–10 most important concepts, terms, or mechanisms the student must understand.
For each, write one precise definition sentence.

KEY FACTS: List 5–8 concrete, specific, measurable facts (dates, values, names, formulas, quantities)
that an expert in this topic would know and that could serve as detective clues.

COMMON MISCONCEPTIONS: List 3–5 things students typically get wrong about this topic.
Each misconception should be a specific wrong belief, not a vague category.

DIFFICULTY CALIBRATION: Given the school type and grade, describe in 2–3 sentences what level of
precision, which sub-topics, and which vocabulary are age-appropriate for this group.
"""

_VALIDATION_SYSTEM = """\
You are a factual accuracy checker for educational content.
You receive numbered "expected student answers" from a detective learning scenario, each labelled with its subject.
For each entry, check whether the stated fact or mechanism is scientifically / historically / mathematically correct.
Output exactly one line per entry:
  OK: [number]
  FLAG: [number] — [one sentence explaining the factual error]
No other text. Be strict: flag anything that is wrong, oversimplified to the point of being misleading, or not verifiable.
"""

# ── Story builder ────────────────────────────────────────────────

def build_story(req: WorkRequest) -> SessionBlueprint:
    research_user = (
        f"Topic: {req.lesson.topic}\n"
        f"School type: {req.lesson.school_type or 'not specified'}\n"
        f"Grade / class: {req.lesson.grade or 'not specified'}\n"
        f"Material provided:\n{req.material[:3000] if req.material else 'none'}"
    )
    research = ask_ollama(_RESEARCH_SYSTEM, research_user, options=_OPTS_RESEARCH)
    print("Research completed.")

    with open("setup_prompt.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    user_message = json.dumps({
        "teacher":        req.teacher.model_dump(),
        "lesson":         req.lesson.model_dump(),
        "material":       req.material,
        "topic_research": research,
    }, ensure_ascii=False)

    raw = ask_ollama(system_prompt, user_message, options=_OPTS_BLUEPRINT)
    try:
        blueprint = SessionBlueprint.from_llm_response(raw)
    except (ValueError, json.JSONDecodeError) as first_err:
        print(f"Blueprint parse failed ({first_err}), retrying with JSON-repair prompt…")
        repair_prompt = (
            "The following text contains a JSON object that has syntax errors. "
            "Output only the corrected, complete, valid JSON — no explanation, no markdown:\n\n"
            + raw[:12000]
        )
        raw2 = ask_ollama("You are a JSON repair tool. Output only valid JSON.",
                          repair_prompt,
                          options={**_OPTS_BLUEPRINT, "temperature": 0.05})
        blueprint = SessionBlueprint.from_llm_response(raw2)

    try:
        entries = "\n\n".join(
            f"[{i}] Subject: {blueprint.topic.core_subject}\n"
            f"Expected answer: {m.expected_student_response}"
            for i, m in enumerate(blueprint.moves)
        )
        val_result = ask_ollama(_VALIDATION_SYSTEM, entries, options=_OPTS_VALIDATE)
        flags = [l for l in val_result.splitlines() if l.strip().startswith("FLAG:")]
        if flags:
            print(f"Validation flags ({len(flags)}):")
            for f_line in flags:
                print(" ", f_line)
    except Exception as e:
        print(f"Validation skipped: {e}")

    return blueprint

# ── Session store ────────────────────────────────────────────────

_sessions:      dict[str, SessionBlueprint] = {}
_session_state: dict[str, dict]             = {}

def _init_state(blueprint: SessionBlueprint) -> dict:
    return {
        "current_move_id":       blueprint.opening.opening_move_id,
        "visited_move_ids":      [],
        "turn_count":            0,
        "correct_count":         0,
        "closed":                False,
        "appeared_character_ids": [],
    }

def _update_appeared_characters(blueprint: SessionBlueprint, state: dict,
                                  visited_move_ids: list[str]) -> None:
    appeared = set(state.get("appeared_character_ids", []))
    for char in blueprint.characters:
        for move_id in char.appears_in_moves:
            if move_id in visited_move_ids:
                appeared.add(char.id)
    # Fallback: if the model generated characters without appears_in_moves,
    # unlock everyone immediately so the interrogation tab isn't empty forever.
    if not appeared and blueprint.characters and all(
        not c.appears_in_moves for c in blueprint.characters
    ):
        appeared = {c.id for c in blueprint.characters}
    state["appeared_character_ids"] = list(appeared)

def _phase_index_for_move(blueprint: SessionBlueprint, move_id: str) -> int:
    move = blueprint.get_move(move_id)
    if not move:
        return 0
    for i, phase in enumerate(blueprint.phases):
        if phase.id == move.phase:
            return i
    return 0

def _closing_line(blueprint: SessionBlueprint, state: dict) -> str:
    total = max(state["turn_count"], 1)
    ratio = state["correct_count"] / total
    if ratio >= 0.70:
        return blueprint.closing.success_line
    elif ratio >= 0.40:
        return blueprint.closing.partial_line
    else:
        return blueprint.closing.fail_line

def _apply_state_signal(
    signal:       str,
    current_move: "Move | None",
    blueprint:    SessionBlueprint,
    state:        dict,
) -> None:
    # Extracted from the inline handler because the original had CLOSE unreachable
    # (it was inside the ADVANCE branch). Now all three signals are first-class.
    if signal == "ADVANCE":
        state["correct_count"] += 1
        if current_move and current_move.type == "closing":
            state["closed"] = True
        elif current_move and current_move.if_correct:
            next_id = current_move.if_correct
            state["current_move_id"] = next_id
            if next_id not in state["visited_move_ids"]:
                state["visited_move_ids"].append(next_id)
    elif signal == "CLOSE":
        state["closed"] = True
    else:  # STAY
        if current_move and current_move.if_incorrect:
            state["current_move_id"] = current_move.if_incorrect

    if state["turn_count"] >= blueprint.session.estimated_turns:
        state["closed"] = True

# ── API ──────────────────────────────────────────────────────────

@app.post("/api/work")
def work(req: WorkRequest):
    print("Request received")
    try:
        blueprint = build_story(req)
        _sessions[blueprint.session_id] = blueprint
        _session_state[blueprint.session_id] = _init_state(blueprint)
        print(f"Blueprint generated: {blueprint.session_id}")
        return blueprint.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Model returned invalid JSON: {e}")
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e}")

@app.post("/api/chat")
def chat(req: ChatRequest):
    blueprint = _sessions.get(req.session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_state.setdefault(req.session_id, _init_state(blueprint))

    if state["closed"]:
        return {
            "reply":                  _closing_line(blueprint, state),
            "phase_index":            len(blueprint.phases) - 1,
            "closed":                 True,
            "appeared_character_ids": state.get("appeared_character_ids", []),
        }

    current_move = blueprint.get_move(state["current_move_id"])
    is_hint = req.message.startswith("[SYSTEM:")

    try:
        reply, signal = run_teacher_agent(
            blueprint, req.message, current_move, req.history,
            visited_move_ids=state.get("visited_move_ids", []),
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e}")

    if not is_hint:
        state["turn_count"] += 1
        if current_move and current_move.id not in state["visited_move_ids"]:
            state["visited_move_ids"].append(current_move.id)
        _apply_state_signal(signal, current_move, blueprint, state)

    _update_appeared_characters(blueprint, state, state["visited_move_ids"])
    phase_index = _phase_index_for_move(blueprint, state["current_move_id"])

    response: dict = {
        "reply":                  reply,
        "phase_index":            phase_index,
        "closed":                 state["closed"],
        "appeared_character_ids": state.get("appeared_character_ids", []),
    }
    if state["closed"]:
        response["closing_line"] = _closing_line(blueprint, state)
    return response

@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    blueprint = _sessions.get(req.session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")

    state = _session_state.setdefault(req.session_id, _init_state(blueprint))

    if state["closed"]:
        closing = _closing_line(blueprint, state)
        def closed_gen():
            yield f"data: {json.dumps({'chunk': closing})}\n\n"
            yield f"data: {json.dumps({'done': True, 'closed': True, 'closing_line': closing, 'phase_index': len(blueprint.phases) - 1, 'appeared_character_ids': state.get('appeared_character_ids', [])})}\n\n"
        return StreamingResponse(
            closed_gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    current_move = blueprint.get_move(state["current_move_id"])
    is_hint = req.message.startswith("[SYSTEM:")

    system_prompt, user_message = _build_teacher_prompts(
        blueprint, req.message, current_move, req.history,
        visited_move_ids=state.get("visited_move_ids", []),
    )

    def event_gen():
        buffer = ""
        try:
            for chunk in ask_ollama_stream(system_prompt, user_message, options=_OPTS_CHAT):
                buffer += chunk
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except requests.RequestException as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # Parse state from completed buffer
        signal = "STAY"
        state_match = re.search(
            r"\[STATE\][:\s]*\n?\s*(ADVANCE|STAY|CLOSE)", buffer, re.IGNORECASE
        )
        if state_match:
            signal = state_match.group(1).upper()

        if not is_hint:
            state["turn_count"] += 1
            if current_move and current_move.id not in state["visited_move_ids"]:
                state["visited_move_ids"].append(current_move.id)
            _apply_state_signal(signal, current_move, blueprint, state)

        _update_appeared_characters(blueprint, state, state["visited_move_ids"])
        phase_index = _phase_index_for_move(blueprint, state["current_move_id"])

        done_data: dict = {
            "done":                   True,
            "state_signal":           signal,
            "phase_index":            phase_index,
            "closed":                 state["closed"],
            "appeared_character_ids": state.get("appeared_character_ids", []),
        }
        if state["closed"]:
            done_data["closing_line"] = _closing_line(blueprint, state)
        yield f"data: {json.dumps(done_data)}\n\n"

    return StreamingResponse(
        event_gen(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

@app.post("/api/interrogate")
def interrogate(req: InterrogateRequest):
    blueprint = _sessions.get(req.session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")

    character = blueprint.get_character(req.character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")

    state = _session_state.get(req.session_id, {})
    appeared = state.get("appeared_character_ids", [])
    # Fallback: if appeared list is empty but characters exist, allow all
    if appeared and req.character_id not in appeared:
        raise HTTPException(status_code=403, detail="Character has not appeared in the story yet")

    system_template = _load_prompt("interrogation_system_prompt.txt")
    system_prompt = system_template.format(
        character_name=character.name,
        character_role=character.role,
        character_personality=character.personality,
        character_voice=character.voice,
        character_knowledge=character.knowledge,
        character_secrets=character.secrets,
        character_ignorant_of=character.ignorant_of,
        language=blueprint.session.language,
    )

    history_text = "(none)"
    if req.history:
        lines = []
        for msg in req.history:
            label = "DETECTIVE" if msg.role == "user" else character.name
            lines.append(f"{label}: {msg.content}")
        history_text = "\n".join(lines)

    user_message = f"CONVERSATION SO FAR:\n{history_text}\n\nDETECTIVE: {req.message}"

    try:
        reply = ask_ollama(system_prompt, user_message, options=_OPTS_CHAT)
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e}")

    return {"reply": reply}

@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    blueprint = _sessions.get(session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _session_state.get(session_id, _init_state(blueprint))
    return {
        "appeared_character_ids": state.get("appeared_character_ids", []),
        "turn_count":             state.get("turn_count", 0),
        "closed":                 state.get("closed", False),
    }

# ── Debug API (all routes gated by /api/debug/ prefix) ──────────

@app.get("/api/debug/{session_id}/state")
def debug_state(session_id: str):
    blueprint = _sessions.get(session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _session_state.get(session_id, _init_state(blueprint))
    current_move = blueprint.get_move(state["current_move_id"])
    return {
        "session_id": session_id,
        "state": state,
        "current_move": dataclasses.asdict(current_move) if current_move else None,
        "blueprint_summary": {
            "session_id":    blueprint.session_id,
            "topic":         blueprint.topic.core_subject,
            "teacher":       blueprint.teacher.name,
            "language":      blueprint.session.language,
            "total_moves":   len(blueprint.moves),
            "total_phases":  len(blueprint.phases),
            "move_ids":      [m.id for m in blueprint.moves],
            "character_ids": [c.id for c in blueprint.characters],
        },
    }

@app.post("/api/debug/{session_id}/advance")
def debug_advance(session_id: str):
    """Force-advance the session without asking the model."""
    blueprint = _sessions.get(session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _session_state.setdefault(session_id, _init_state(blueprint))
    current_move = blueprint.get_move(state["current_move_id"])
    if current_move and current_move.id not in state["visited_move_ids"]:
        state["visited_move_ids"].append(current_move.id)
    _apply_state_signal("ADVANCE", current_move, blueprint, state)
    _update_appeared_characters(blueprint, state, state["visited_move_ids"])
    return {"ok": True, "new_move_id": state["current_move_id"], "closed": state["closed"]}

@app.post("/api/debug/{session_id}/goto")
def debug_goto(session_id: str, req: DebugGotoRequest):
    """Jump directly to any move by ID."""
    blueprint = _sessions.get(session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")
    if not blueprint.get_move(req.move_id):
        raise HTTPException(status_code=404, detail=f"Move '{req.move_id}' not found")
    state = _session_state.setdefault(session_id, _init_state(blueprint))
    state["current_move_id"] = req.move_id
    if req.move_id not in state["visited_move_ids"]:
        state["visited_move_ids"].append(req.move_id)
    return {"ok": True, "current_move_id": req.move_id}

@app.post("/api/debug/{session_id}/unlock_chars")
def debug_unlock_chars(session_id: str):
    """Make all characters available in the interrogation tab immediately."""
    blueprint = _sessions.get(session_id)
    if not blueprint:
        raise HTTPException(status_code=404, detail="Session not found")
    state = _session_state.setdefault(session_id, _init_state(blueprint))
    state["appeared_character_ids"] = [c.id for c in blueprint.characters]
    return {"ok": True, "unlocked": state["appeared_character_ids"]}

# ── Serve frontend ───────────────────────────────────────────────
app.mount("/", StaticFiles(directory=".", html=True), name="static")
