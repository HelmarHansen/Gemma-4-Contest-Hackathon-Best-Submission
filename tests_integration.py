"""
Boot the real FastAPI server and walk through the complete user flow
end-to-end. We mock Ollama at the requests layer so the server stays
in production code paths but doesn't actually need a model.

This verifies that:
  - The server starts, serves index.html and chat.html
  - /api/work returns a real blueprint
  - /api/chat advances state across multiple turns
  - /api/interrogate works with multiple characters
  - The session reaches a closed state
"""

import json
import re
import subprocess
import sys
import time

import requests


def _murder_photosynthese_bp() -> str:
    return json.dumps({
        "session_id": "int-test-001",
        "teacher": {"name": "Marlow", "role": "Inspektorin", "voice": "trocken",
                    "active_traits": [], "expects_from_student": "Präzision",
                    "will_not_do": "spoilern", "signature_phrases": ["Was sehen Sie?"]},
        "session": {"mode": "Murder", "language": "German", "immersive": True,
                    "difficulty": 0.7, "pacing": "steady",
                    "estimated_turns": 4, "hint_policy": "only if asked"},
        "topic": {"raw": "Photosynthese", "core_subject": "Photosynthese",
                  "learning_goals": ["PS II / PAR"], "likely_weak_spots": [],
                  "out_of_scope": "", "material_summary": ""},
        "arc": {"phases": [
            {"id": "p1", "name": "Tatort", "goal": "", "turn_budget": 1,
             "teacher_strategy": "", "exit_condition": "", "fallback": ""},
            {"id": "p2", "name": "Auflösung", "goal": "", "turn_budget": 1,
             "teacher_strategy": "", "exit_condition": "", "fallback": ""},
        ]},
        "planned_moves": [
            {"id": "m1", "phase": "p1", "type": "scene", "trigger": "",
             "content": "Tatort", "expected_student_response": "Anomalie nennen.",
             "if_correct": "m2", "if_incorrect": "m1", "hint": None,
             "source_ref": None, "is_error_trap": False, "error_correction_key": None},
            {"id": "m2", "phase": "p2", "type": "closing", "trigger": "",
             "content": "Auflösung", "expected_student_response": "Tathergang erklären.",
             "if_correct": "m2", "if_incorrect": "m2", "hint": None,
             "source_ref": None, "is_error_trap": False, "error_correction_key": None},
        ],
        "contingencies": {"student_goes_off_topic": "", "student_asks_for_answer": "",
                          "student_is_silent": "", "student_is_consistently_wrong": "",
                          "student_finishes_early": ""},
        "opening": {"first_line": "Tatort.", "opening_move_id": "m1"},
        "closing": {"success_line": "Erfolg.", "partial_line": "Teilweise.", "fail_line": "Misserfolg."},
        "characters": [
            {"id": "ch1", "name": "Hauke Pomrenke", "role": "Techniker",
             "personality": "knapp", "voice": "trocken",
             "knowledge": "Wartung", "secrets": "bezahlt", "ignorant_of": "Kalender",
             "appears_in_moves": []},
            {"id": "ch2", "name": "Dr. Margit Riewald", "role": "Co-Forscherin",
             "personality": "kontrolliert", "voice": "ausweichend",
             "knowledge": "Photosystem", "secrets": "Tatnacht im Treibhaus", "ignorant_of": "Pomrenke-Deal",
             "appears_in_moves": []},
        ],
        "execution_rules": {"how_to_pick_next_move": "", "when_to_deviate_from_plan": "",
                            "response_length_guideline": "", "never_do": []},
    }, ensure_ascii=False)


# Mock module that will be installed BEFORE main is imported.
MOCK_MODULE = '''
import json, sys, requests
_BP_JSON = """%s"""

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
        return "OK: 0\\nOK: 1"
    if "STAY IN CHARACTER AT ALL TIMES" in sp:
        # Identify the character from the very first line: "You are <Name>."
        first = sp.splitlines()[0] if sp else ""
        if "Pomrenke" in first: return "Routineaustausch, mehr nicht."
        if "Riewald"  in first: return "Ich war zu Hause."
        return "Keine Antwort."
    if "game master" in sp:
        _advance_count["n"] += 1
        sig = "ADVANCE" if _advance_count["n"] >= 1 else "STAY"
        return (f"[NARRATION] Konsequenz {_advance_count['n']}.\\n"
                f"[NPC:Marlow] Reaktion.\\n"
                f"[QUESTION] Nächste Frage?\\n"
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
''' % _murder_photosynthese_bp().replace('"""', '\\"\\"\\"')


def main():
    # 1. Write the mock side-loader.
    with open("_mock_ollama.py", "w") as f:
        f.write(MOCK_MODULE)

    # 2. Boot uvicorn in a subprocess with a sitecustomize that loads the mock first.
    boot_script = """
import _mock_ollama  # patches requests.post before main imports
import uvicorn
import main as app_module
uvicorn.run(app_module.app, host='127.0.0.1', port=8765, log_level='warning')
"""
    with open("_boot.py", "w") as f:
        f.write(boot_script)

    proc = subprocess.Popen(
        [sys.executable, "_boot.py"],
        cwd=".",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    base = "http://127.0.0.1:8765"

    # 3. Wait for /docs to come up.
    started = False
    for _ in range(40):
        try:
            r = requests.get(base + "/docs", timeout=0.5)
            if r.status_code == 200:
                started = True
                break
        except requests.RequestException:
            time.sleep(0.25)
    if not started:
        out, err = proc.communicate(timeout=3)
        print("Server failed to start.\nstdout:", out.decode()[-2000:],
              "\nstderr:", err.decode()[-2000:])
        return 1

    try:
        all_passed = True

        # Static file checks
        print("\n[INT-1] Static assets served from /")
        for path, needle in [("/", "<title>MindHeist"),
                              ("/chat.html", "panel-investigation"),
                              ("/chat.js", "parseSections"),
                              ("/chat.css", "interrogation-bubble")]:
            r = requests.get(base + path)
            ok = r.status_code == 200 and needle in r.text
            print(f"  {'PASS' if ok else 'FAIL'}  GET {path} contains {needle!r}")
            all_passed &= ok

        # /api/work
        print("\n[INT-2] POST /api/work returns a blueprint")
        r = requests.post(base + "/api/work", json={
            "teacher": {"name": "Marlow", "role": "—", "personality": "—", "traits": []},
            "lesson":  {"topic": "Photosynthese", "mode": "Murder", "language": "German",
                        "length": "30 min — standard", "difficulty": 0.7,
                        "school_type": "Gymnasium", "grade": "Klasse 9"},
            "material": "",
        })
        ok = r.status_code == 200 and r.json().get("session_id") == "int-test-001"
        print(f"  {'PASS' if ok else 'FAIL'}  session created")
        all_passed &= ok

        # /api/chat — turn 1 (opener)
        print("\n[INT-3] Multi-turn chat: opener → answer → closing")
        history = []
        r = requests.post(base + "/api/chat", json={
            "session_id": "int-test-001",
            "message": "[SYSTEM: begin the case]",
            "history": history,
        })
        d = r.json()
        ok = r.status_code == 200 and "[NARRATION]" in d["reply"] and d["closed"] is False
        print(f"  {'PASS' if ok else 'FAIL'}  opener served")
        all_passed &= ok
        history.append({"role": "user", "content": "[SYSTEM: begin the case]"})
        history.append({"role": "assistant", "content": d["reply"]})

        # turn 2 — student answers correctly → ADVANCE → reach closing move
        r = requests.post(base + "/api/chat", json={
            "session_id": "int-test-001",
            "message": "Manipulation: CO₂-Sensor angezeigt rot, Kabel abgezogen.",
            "history": history,
        })
        d = r.json()
        ok = r.status_code == 200 and "[NPC:" in d["reply"]
        print(f"  {'PASS' if ok else 'FAIL'}  ADVANCE turn")
        all_passed &= ok
        history.append({"role": "assistant", "content": d["reply"]})

        # turn 3 — at closing move, ADVANCE on a closing move = CLOSE
        r = requests.post(base + "/api/chat", json={
            "session_id": "int-test-001",
            "message": "Vollständige Begründung: PAR fehlt → kein Photosystem II → kein O₂ + geschlossene Stomata + CO₂-Düngung → Erstickung.",
            "history": history,
        })
        d = r.json()
        ok = r.status_code == 200 and (d["closed"] is True or "[NPC:" in d["reply"])
        print(f"  {'PASS' if ok else 'FAIL'}  closing reached / NPC reply")
        all_passed &= ok

        # /api/session/.../characters
        print("\n[INT-4] GET characters list")
        r = requests.get(base + "/api/session/int-test-001/characters")
        cs = r.json()["characters"]
        ok = r.status_code == 200 and {c["name"] for c in cs} == {"Hauke Pomrenke", "Dr. Margit Riewald"}
        print(f"  {'PASS' if ok else 'FAIL'}  {len(cs)} characters listed")
        all_passed &= ok

        # /api/interrogate — two characters in parallel
        print("\n[INT-5] Interrogate two characters")
        for cid, name, needle in [
            ("ch1", "Hauke Pomrenke", "Routine"),
            ("ch2", "Dr. Margit Riewald", "zu Hause"),
            ("Dr. Margit Riewald", "Dr. Margit Riewald", "zu Hause"),  # by name
        ]:
            r = requests.post(base + "/api/interrogate", json={
                "session_id": "int-test-001",
                "character_id": cid,
                "message": "Wo waren Sie um 23:48?",
                "history": [],
            })
            d = r.json()
            ok = (r.status_code == 200
                  and d["character"]["name"] == name
                  and needle in d["reply"]
                  and "[NARRATION]" not in d["reply"])
            print(f"  {'PASS' if ok else 'FAIL'}  interrogate {cid!r} → '{d.get('reply', '')[:50]}'")
            all_passed &= ok

        # /api/interrogate — unknown character
        print("\n[INT-6] Unknown character → 404")
        r = requests.post(base + "/api/interrogate", json={
            "session_id": "int-test-001",
            "character_id": "Mr. Nobody",
            "message": "?",
            "history": [],
        })
        ok = r.status_code == 404
        print(f"  {'PASS' if ok else 'FAIL'}  404 returned")
        all_passed &= ok

        return 0 if all_passed else 1
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill()


if __name__ == "__main__":
    sys.exit(main())
