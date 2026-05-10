import json
import re
import requests
from dataclasses import dataclass, field, asdict
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "gemma4:31b"

# ── Blueprint dataclasses ────────────────────────────────────────

@dataclass
class Teacher:
    name:              str
    role:              str
    voice:             str
    active_traits:     list[str]
    expects_from_student: str
    will_not_do:       str
    signature_phrases: list[str]

@dataclass
class Session:
    mode:             str
    language:         str
    immersive:        bool
    difficulty:       float
    pacing:           str
    estimated_turns:  int
    hint_policy:      str

@dataclass
class Topic:
    raw:               str
    core_subject:      str
    learning_goals:    list[str]
    likely_weak_spots: list[str]
    out_of_scope:      str
    material_summary:  str

@dataclass
class Phase:
    id:               str
    name:             str
    goal:             str
    turn_budget:      int
    teacher_strategy: str
    exit_condition:   str
    fallback:         str

@dataclass
class Move:
    id:                        str
    phase:                     str
    type:                      str
    trigger:                   str
    content:                   str
    expected_student_response: str
    if_correct:                str
    if_incorrect:              str
    hint:                      str | None

@dataclass
class Contingencies:
    student_goes_off_topic:        str
    student_asks_for_answer:       str
    student_is_silent:             str
    student_is_consistently_wrong: str
    student_finishes_early:        str

@dataclass
class Opening:
    first_line:      str
    opening_move_id: str

@dataclass
class Closing:
    success_line: str
    partial_line: str
    fail_line:    str

@dataclass
class ExecutionRules:
    how_to_pick_next_move:       str
    when_to_deviate_from_plan:   str
    response_length_guideline:   str
    never_do:                    list[str]

@dataclass
class SessionBlueprint:
    session_id:      str
    teacher:         Teacher
    session:         Session
    topic:           Topic
    phases:          list[Phase]
    moves:           list[Move]
    contingencies:   Contingencies
    opening:         Opening
    closing:         Closing
    execution_rules: ExecutionRules
    _move_index: dict[str, Move] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._move_index = {m.id: m for m in self.moves}

    def get_move(self, move_id: str) -> Move | None:
        return self._move_index.get(move_id)

    def get_opening_move(self) -> Move | None:
        return self.get_move(self.opening.opening_move_id)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_move_index", None)
        return d

    @classmethod
    def from_llm_response(cls, raw: str) -> "SessionBlueprint":
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in model response")
        data = json.loads(match.group())

        return cls(
            session_id=data["session_id"],
            teacher=Teacher(**data["teacher"]),
            session=Session(**data["session"]),
            topic=Topic(**data["topic"]),
            phases=[Phase(**p) for p in data["arc"]["phases"]],
            moves=[Move(**m) for m in data["planned_moves"]],
            contingencies=Contingencies(**data["contingencies"]),
            opening=Opening(**data["opening"]),
            closing=Closing(**data["closing"]),
            execution_rules=ExecutionRules(**data["execution_rules"]),
        )

# ── Request schema ───────────────────────────────────────────────

class TeacherInput(BaseModel):
    name:        str
    role:        str
    personality: str
    traits:      list[str]

class LessonInput(BaseModel):
    topic:      str
    mode:       str
    language:   str
    length:     str
    difficulty: float

class WorkRequest(BaseModel):
    teacher:  TeacherInput
    lesson:   LessonInput
    material: str = ""  
# ── Ollama helper ────────────────────────────────────────────────

def ask_ollama(system_prompt: str, user_message: str) -> str:
    response = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "stream": False,
    })
    response.raise_for_status()
    return response.json()["message"]["content"]

def run_teacher_agent(
    blueprint: SessionBlueprint,
    user_prompt: str) -> str:

    system_prompt = f"""
        You are a game master running an immersive noir detective investigation.
        The player is the detective. You narrate the world and voice all NPCs.

        Your narrator persona:
        - Name: {blueprint.teacher.name}
        - Role: {blueprint.teacher.role}
        - Voice: {blueprint.teacher.voice}

        Your traits as game master:
        {json.dumps(blueprint.teacher.active_traits, ensure_ascii=False)}

        Signature phrases you use:
        {json.dumps(blueprint.teacher.signature_phrases, ensure_ascii=False)}

        ABSOLUTE RULES — never break these:
        {blueprint.teacher.will_not_do}

        GAME MASTER PRINCIPLES:
        1. NEVER say "correct", "wrong", "well done", or anything that sounds like a teacher.
        2. If the detective shows CORRECT knowledge of the topic: reward with story progress — a suspect
           breaks down and confesses a detail, a hidden compartment clicks open, a witness finally talks.
        3. If the detective is WRONG or vague: complicate the story — the witness clams up, the lead
           goes cold, a new suspect muddies the waters, time is wasted. Let them feel the dead end.
        4. Play every NPC with a distinct, vivid voice. Snap between narrator and character dialogue cleanly.
        5. Keep each response to 3-6 sentences — cinematic, tense, sensory. Rain on glass. Cigarette smoke.
           The creak of an old chair. Make it FEEL like a crime scene.
        6. Never volunteer information the detective didn't earn through correct reasoning.
        7. The mystery's solution is locked behind topic knowledge. Clues are facts in disguise.
        8. Do NOT break immersion. Do NOT explain the game. Do NOT reference the blueprint.
        """

    blueprint_json = json.dumps(
        blueprint.to_dict(),
        ensure_ascii=False,
        indent=2
    )

    user_message = f"""
        CASE FILE (full investigation blueprint — for your eyes only as game master):
        {blueprint_json}

        DETECTIVE'S ACTION / STATEMENT:
        {user_prompt}

        React in character. Advance or complicate the story based on whether the detective's response
        demonstrates correct knowledge of the embedded topic. Do NOT explain what they got right or wrong —
        show it through story consequences. End on a hook that draws them deeper.
        """

    return ask_ollama(system_prompt, user_message)


# ── Story builder ────────────────────────────────────────────────

def build_story(req: WorkRequest) -> SessionBlueprint:
    with open("setup_prompt.txt", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    user_message = json.dumps({
        "teacher": req.teacher.model_dump(),
        "lesson":  req.lesson.model_dump(),
        "material": req.material,
    }, ensure_ascii=False)

    raw = ask_ollama(system_prompt, user_message)
    return SessionBlueprint.from_llm_response(raw)

# ── Session store ────────────────────────────────────────────────

_sessions: dict[str, SessionBlueprint] = {}

# ── Chat schema ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:    str   # "user" or "teacher"
    content: str

class ChatRequest(BaseModel):
    session_id: str
    message:    str
    history:    list[ChatMessage] = []

# ── API ──────────────────────────────────────────────────────────

@app.post("/api/work")
def work(req: WorkRequest):
    print("Request received")
    try:
        blueprint = build_story(req)
        _sessions[blueprint.session_id] = blueprint
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
    try:
        reply = run_teacher_agent(blueprint, req.message)
        return {"reply": reply}
    except requests.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ollama unreachable: {e}")

# ── Serve frontend ───────────────────────────────────────────────
app.mount("/", StaticFiles(directory=".", html=True), name="static")