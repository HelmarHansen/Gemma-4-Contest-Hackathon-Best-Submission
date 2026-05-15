
import json, sys, requests
_BP_JSON = """{"session_id": "int-test-001", "teacher": {"name": "Marlow", "role": "Inspektorin", "voice": "trocken", "active_traits": [], "expects_from_student": "Präzision", "will_not_do": "spoilern", "signature_phrases": ["Was sehen Sie?"]}, "session": {"mode": "Murder", "language": "German", "immersive": true, "difficulty": 0.7, "pacing": "steady", "estimated_turns": 4, "hint_policy": "only if asked"}, "topic": {"raw": "Photosynthese", "core_subject": "Photosynthese", "learning_goals": ["PS II / PAR"], "likely_weak_spots": [], "out_of_scope": "", "material_summary": ""}, "arc": {"phases": [{"id": "p1", "name": "Tatort", "goal": "", "turn_budget": 1, "teacher_strategy": "", "exit_condition": "", "fallback": ""}, {"id": "p2", "name": "Auflösung", "goal": "", "turn_budget": 1, "teacher_strategy": "", "exit_condition": "", "fallback": ""}]}, "planned_moves": [{"id": "m1", "phase": "p1", "type": "scene", "trigger": "", "content": "Tatort", "expected_student_response": "Anomalie nennen.", "if_correct": "m2", "if_incorrect": "m1", "hint": null, "source_ref": null, "is_error_trap": false, "error_correction_key": null}, {"id": "m2", "phase": "p2", "type": "closing", "trigger": "", "content": "Auflösung", "expected_student_response": "Tathergang erklären.", "if_correct": "m2", "if_incorrect": "m2", "hint": null, "source_ref": null, "is_error_trap": false, "error_correction_key": null}], "contingencies": {"student_goes_off_topic": "", "student_asks_for_answer": "", "student_is_silent": "", "student_is_consistently_wrong": "", "student_finishes_early": ""}, "opening": {"first_line": "Tatort.", "opening_move_id": "m1"}, "closing": {"success_line": "Erfolg.", "partial_line": "Teilweise.", "fail_line": "Misserfolg."}, "characters": [{"id": "ch1", "name": "Hauke Pomrenke", "role": "Techniker", "personality": "knapp", "voice": "trocken", "knowledge": "Wartung", "secrets": "bezahlt", "ignorant_of": "Kalender", "appears_in_moves": []}, {"id": "ch2", "name": "Dr. Margit Riewald", "role": "Co-Forscherin", "personality": "kontrolliert", "voice": "ausweichend", "knowledge": "Photosystem", "secrets": "Tatnacht im Treibhaus", "ignorant_of": "Pomrenke-Deal", "appears_in_moves": []}], "execution_rules": {"how_to_pick_next_move": "", "when_to_deviate_from_plan": "", "response_length_guideline": "", "never_do": []}}"""

_advance_count = {"n": 0}
class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

def _route(sp, up):
    sp = sp or ""
    if "curriculum analyst" in sp:
        return json.dumps({"core_subject": "Photosynthese", "topic_summary": "...",
                           "core_concepts": [{"term": "PS II", "definition": "PAR ~680 nm"}],
                           "key_facts": ["PAR"], "misconceptions": [],
                           "difficulty_calibration": "K9", "task_formats": [], "story_hooks": []})
    if "exam-preparation specialist" in sp:
        return json.dumps({"task_count": 2, "tasks": []})
    if "case architect" in sp:
        return _BP_JSON
    if "factual accuracy checker" in sp:
        return "OK: 0\nOK: 1"
    if "STAY IN CHARACTER AT ALL TIMES" in sp:
        # Identify the character from the very first line: "You are <Name>."
        first = sp.splitlines()[0] if sp else ""
        if "Pomrenke" in first: return "Routineaustausch, mehr nicht."
        if "Riewald"  in first: return "Ich war zu Hause."
        return "Keine Antwort."
    if "game master" in sp:
        _advance_count["n"] += 1
        sig = "ADVANCE" if _advance_count["n"] >= 1 else "STAY"
        return (f"[NARRATION] Konsequenz {_advance_count['n']}.\n"
                f"[NPC:Marlow] Reaktion.\n"
                f"[QUESTION] Nächste Frage?\n"
                f"[STATE] {sig}")
    return "ok"

class _Stream:
    def __init__(self, content): self.content = content
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def raise_for_status(self): pass
    def iter_lines(self):
        yield json.dumps({"message": {"content": self.content}, "done": True}).encode()

def patched_post(url, json=None, stream=False, timeout=None, **kw):
    body = json or {}
    msgs = body.get("messages", [])
    sp = msgs[0]["content"] if msgs else ""
    up = msgs[1]["content"] if len(msgs) > 1 else ""
    content = _route(sp, up)
    if stream: return _Stream(content)
    return _Resp({"message": {"content": content}})

requests.post = patched_post
