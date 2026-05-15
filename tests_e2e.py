"""
End-to-end smoke tests for MindHeist.

These tests mock the Ollama backend so we can exercise the FastAPI app
without a running model. They cover:

  1. App boots and `/api/work` returns a valid blueprint dict.
  2. `/api/work/stream` (SSE) emits the three-stage progress envelope.
  3. `/api/chat` returns a structured reply and tracks state.
  4. `/api/session/{id}/characters` lists the NPCs in the blueprint.
  5. `/api/interrogate` returns a reply for a named character.

Run:  python3 tests_e2e.py
"""

import json
import sys
import re

# Mock Ollama before importing the app.
import main


def _murder_photosynthese_blueprint() -> str:
    """Realistic, fully validated blueprint for the photosynthesis murder case."""
    bp = {
        "session_id": "treibhaus3-2026",
        "teacher": {
            "name": "Inspektorin Marlow",
            "role": "Ermittlungsleiterin der Kripo Altenstein",
            "voice": "trocken, präzise, ungeduldig",
            "active_traits": ["Strict", "Storyteller"],
            "expects_from_student": "präzise Begründungen mit Wellenlängen und Stomata-Regulation",
            "will_not_do": "Konzepte aussprechen, statt Beweise zeigen",
            "signature_phrases": ["Was sehen Sie?", "Was passt nicht?"],
        },
        "session": {
            "mode": "Murder", "language": "German", "immersive": True,
            "difficulty": 0.7, "pacing": "steady",
            "estimated_turns": 7, "hint_policy": "only if asked",
        },
        "topic": {
            "raw": "Photosynthese — Lichtreaktion, Stomata-Regulation",
            "core_subject": "Photosynthese",
            "learning_goals": [
                "Photosystem II benötigt PAR (~430/680 nm)",
                "Stomata öffnen bei PAR-Licht, schließen unter IR-only/Dunkel",
                "Stoffbilanz 6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂",
            ],
            "likely_weak_spots": ["Verwechslung PAR/UV/IR", "Stomata-Regulation"],
            "out_of_scope": "Calvin-Zyklus-Details, Chemiosmose",
            "material_summary": "",
        },
        "arc": {"phases": [
            {"id": "p1", "name": "Tatort", "goal": "Anomalien erkennen", "turn_budget": 1,
             "teacher_strategy": "Szene zeigen", "exit_condition": "CO₂-Sensor-Anomalie benannt", "fallback": "weiterer Hinweis"},
            {"id": "p2", "name": "Untersuchung", "goal": "Lampenspektrum und Stomata", "turn_budget": 3,
             "teacher_strategy": "Befragungen und Notizen", "exit_condition": "IR ≠ PAR + Stomata-Regulation", "fallback": "Wiederholung"},
            {"id": "p3", "name": "Wende", "goal": "CO₂-Bilanz", "turn_budget": 1,
             "teacher_strategy": "Düngeflasche", "exit_condition": "Bilanz erklärt", "fallback": "Hilfe"},
            {"id": "p4", "name": "Konfrontation", "goal": "Karten-Log", "turn_budget": 1,
             "teacher_strategy": "Sandhoff zeigt Log", "exit_condition": "Riewald entlarvt", "fallback": "—"},
            {"id": "p5", "name": "Auflösung", "goal": "Tathergang", "turn_budget": 1,
             "teacher_strategy": "Schlussfolgerung", "exit_condition": "vollständige Erklärung", "fallback": "—"},
        ]},
        "planned_moves": [
            {
                "id": "m01_szene", "phase": "p1", "type": "scene",
                "trigger": "Eintritt ins Treibhaus",
                "content": "Treibhaus 3, 06:42. Brendler liegt am Boden, blau angelaufen. Über dem Pflanzentisch hängen vier neue Strahler — Typenschild 850–940 nm. Der O₂-Sensor an Tisch 3 verläuft flach seit 23:48. Der CO₂-Sensor ist rot, das Datenkabel hängt lose.",
                "expected_student_response": "Die hohe CO₂-Anzeige + abgekoppeltes Kabel deutet auf vorsätzliche Manipulation; die nm-Werte der Strahler sind kein PAR-Licht.",
                "if_correct": "m02_pomrenke", "if_incorrect": "m01_szene",
                "hint": "Welchen Wellenlängenbereich braucht Photosynthese?",
                "source_ref": "Biologie Kl. 9: Photosynthese — Lichtreaktion",
                "is_error_trap": False, "error_correction_key": None,
            },
            {
                "id": "m02_pomrenke", "phase": "p2", "type": "interrogation",
                "trigger": "Befragung Pomrenke",
                "content": "Pomrenke (Techniker) reicht das Wartungsprotokoll: '23:47 — UV → IR-Tausch, gemäß Brendlers Anweisung.' Die alten Strahler liegen im Lagerraum, beschriftet 'PAR 380–720 nm'.",
                "expected_student_response": "IR (>700 nm) regt Photosystem II nicht an — ohne PAR keine Lichtreaktion, kein O₂.",
                "if_correct": "m03_zettel", "if_incorrect": "m02_pomrenke",
                "hint": "Wellenlängenbereich der Chlorophyll-Absorption.",
                "source_ref": "Biologie Kl. 9: Photosystem II / Chlorophyll-Absorption",
                "is_error_trap": False, "error_correction_key": None,
            },
            {
                "id": "m03_zettel", "phase": "p2", "type": "clue",
                "trigger": "Notizzettel auf Riewalds Tisch",
                "content": "Handgeschriebener Zettel: 'Brendler wollte Stomata-Verhalten unter IR testen. Mit reiner IR-Beleuchtung bleiben die Stomata geöffnet → CO₂-Aufnahme möglich.'",
                "expected_student_response": "Falsche Behauptung — Stomata schließen unter reiner IR-Beleuchtung; sie öffnen unter PAR. Folge: keine CO₂-Aufnahme durch die Pflanzen.",
                "if_correct": "m04_dueger", "if_incorrect": "m03_zettel",
                "hint": "Stomata-Regulation: welche Wellenlängen öffnen sie?",
                "source_ref": "Biologie Kl. 9: Stomata-Regulation",
                "is_error_trap": True,
                "error_correction_key": "Stomata öffnen unter PAR (400–700 nm), nicht unter Infrarot.",
            },
            {
                "id": "m04_dueger", "phase": "p3", "type": "clue",
                "trigger": "CO₂-Düngeflasche",
                "content": "Eine CO₂-Düngeflasche neben dem Tisch ist halbleer; laut Lieferschein war sie gestern voll.",
                "expected_student_response": "Ohne Lichtreaktion kein CO₂-Verbrauch durch Pflanzen + ohne offene Stomata kein Uptake → CO₂ reichert sich in der versiegelten Kammer an.",
                "if_correct": "m05_sandhoff", "if_incorrect": "m04_dueger",
                "hint": "Stoffbilanz der Photosynthese.",
                "source_ref": "Biologie Kl. 9: Photosynthese — Stoffbilanz",
                "is_error_trap": False, "error_correction_key": None,
            },
            {
                "id": "m05_sandhoff", "phase": "p4", "type": "revelation",
                "trigger": "Sandhoff zeigt Karten-Log",
                "content": "Sandhoff legt das Magnetkartenprotokoll vor: Brendler 06:32, Pomrenke 22:48, Riewald 03:14.",
                "expected_student_response": "Riewald war entgegen ihrer Aussage in der Tatnacht im Treibhaus — wahrscheinlich zur Kontrolle der CO₂-Anreicherung.",
                "if_correct": "m06_closing", "if_incorrect": "m05_sandhoff",
                "hint": "Karten-Log vs. Riewalds Alibi.",
                "source_ref": "Falldokumentation Treibhaus 3",
                "is_error_trap": False, "error_correction_key": None,
            },
            {
                "id": "m06_closing", "phase": "p5", "type": "closing",
                "trigger": "Auflösung",
                "content": "Marlow blickt auf. Die Akte liegt offen. „Erklären Sie mir den Tathergang — wer, wie, womit, warum.\"",
                "expected_student_response": "Riewald (Motiv: Autorenschaftsstreit) ließ über Pomrenke die PAR-Lampen gegen IR-Strahler tauschen. Ohne PAR keine Lichtreaktion (keine O₂-Produktion) und geschlossene Stomata (kein CO₂-Uptake). Die angeschlossene CO₂-Düngung ließ den CO₂-Gehalt über Nacht tödlich ansteigen. Brendler erstickte am Morgen.",
                "if_correct": "m06_closing", "if_incorrect": "m06_closing",
                "hint": "Wer + Wie + Womit + Warum.",
                "source_ref": "Biologie Kl. 9: Photosynthese — Synthese",
                "is_error_trap": False, "error_correction_key": None,
            },
        ],
        "contingencies": {
            "student_goes_off_topic": "Marlow zieht zurück zur Akte.",
            "student_asks_for_answer": "Hinweis aus Wartungsprotokoll oder Stomata-Regel.",
            "student_is_silent": "Pomrenke wird ungeduldig.",
            "student_is_consistently_wrong": "Hint-Eskalation: Pomrenke nennt PAR.",
            "student_finishes_early": "Marlow stellt zusätzliche Frage zur Stoffbilanz.",
        },
        "opening": {
            "first_line": "Treibhaus 3, 06:42 — kalt-blaues Notlicht, der Botaniker tot am Boden.",
            "opening_move_id": "m01_szene",
        },
        "closing": {
            "success_line": "Marlow nickt knapp. „Der Staatsanwalt wird Sie hören wollen.\"",
            "partial_line": "„Sie haben das Wesentliche — aber die Bilanz fehlt.\"",
            "fail_line":    "„Schließen Sie die Akte. Wir machen das morgen früh nochmal.\"",
        },
        "characters": [
            {"id": "ch_riewald", "name": "Dr. Margit Riewald", "role": "Co-Forscherin",
             "personality": "kontrolliert, defensiv unter Druck",
             "voice": "leise, präzise, ausweichend",
             "knowledge": "kennt das gesamte Photosystem-Setup, Lampenspektren, Stoffbilanz",
             "secrets": "war in der Tatnacht im Treibhaus; Streit um Autorenschaft",
             "ignorant_of": "Pomrenkes konkrete Bezahlung",
             "appears_in_moves": ["m03_zettel", "m05_sandhoff"]},
            {"id": "ch_pomrenke", "name": "Hauke Pomrenke", "role": "Techniker",
             "personality": "kurz angebunden, gereizt unter Druck",
             "voice": "knapp, defensiv",
             "knowledge": "Wartungsprotokoll, Lampenspektren UV/PAR/IR",
             "secrets": "wurde von Riewald bezahlt",
             "ignorant_of": "Brendlers persönlichen Kalender",
             "appears_in_moves": ["m02_pomrenke"]},
            {"id": "ch_sandhoff", "name": "Vera Sandhoff", "role": "Sicherheitschefin",
             "personality": "neutral-distanziert",
             "voice": "sachlich",
             "knowledge": "Magnetkarten-Log, CO₂-Toxizitätswerte",
             "secrets": "kennt CO₂-Werte aus eigenem Projekt",
             "ignorant_of": "den Inhalt des Wartungsprotokolls",
             "appears_in_moves": ["m05_sandhoff"]},
        ],
        "execution_rules": {
            "how_to_pick_next_move": "Folge if_correct bei richtiger Antwort, if_incorrect sonst.",
            "when_to_deviate_from_plan": "Nur bei klarer Verständnislücke.",
            "response_length_guideline": "3–5 Sätze Narration, 1–3 NPC-Sätze.",
            "never_do": ["Konzepte aussprechen", "Lehrervokabular benutzen"],
        },
    }
    return json.dumps(bp, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Mock the Ollama HTTP layer.
# ---------------------------------------------------------------------------

def _route_mock(system_prompt: str, user_message: str) -> str:
    """Dispatch to a pre-baked response based on which system prompt is in play."""
    sp = system_prompt or ""
    if "curriculum analyst" in sp:
        return json.dumps({
            "core_subject": "Photosynthese",
            "topic_summary": "Lichtreaktion und Stomata-Regulation.",
            "core_concepts": [
                {"term": "Photosystem II", "definition": "absorbiert maximal bei ~680 nm."},
                {"term": "Stomata", "definition": "Schließzellen regulieren Gasaustausch."},
            ],
            "key_facts": ["Photosynthese: 6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂"],
            "misconceptions": [{"wrong_belief": "Stomata öffnen unter IR.",
                                "correction": "Stomata öffnen unter PAR (400–700 nm)."}],
            "difficulty_calibration": "Klasse 9 Gymnasium.",
            "task_formats": ["explain_mechanism", "identify_error"],
            "story_hooks": ["sabotierter Lampentausch"],
        })
    if "exam-preparation specialist" in sp:
        return json.dumps({"task_count": 6, "tasks": [
            {"id": "t01", "concept": "Photosystem II", "format": "explain_mechanism", "difficulty": 0.6,
             "core_knowledge": "PAR vs. IR", "expected_answer": "IR regt Photosystem II nicht an.",
             "is_buffer": False, "story_hook": "Wartungsprotokoll Lampentausch"},
            {"id": "t02", "concept": "Stomata", "format": "identify_error", "difficulty": 0.65,
             "core_knowledge": "Stomata-Regulation", "expected_answer": "Stomata schließen unter IR.",
             "is_buffer": False, "story_hook": "Notizzettel auf Riewalds Tisch"},
        ]})
    if "case architect" in sp:
        return _murder_photosynthese_blueprint()
    if "factual accuracy checker" in sp:
        return "OK: 0\nOK: 1\nOK: 2\nOK: 3\nOK: 4\nOK: 5"
    # Order matters: the interrogation prompt mentions "game master" in its rules,
    # so check the interrogation marker BEFORE the game-master dispatcher.
    if "STAY IN CHARACTER AT ALL TIMES" in sp:
        return "Routineaustausch. Wenn Sie etwas falsch finden, fragen Sie jemanden mit Doktortitel."
    if "game master" in sp:
        return ("[NARRATION] Das Notlicht über dem Tisch flackert. Der CO₂-Sensor schlägt rot aus, das Datenkabel hängt lose. Über dem Pflanzentisch summen vier neue Strahler.\n\n"
                "[NPC:Inspektorin Marlow] „Was sehen Sie zuerst?\"\n\n"
                "[QUESTION] Was an dieser Szene passt nicht zu einem normalen Treibhaus-Tod?\n\n"
                "[STATE] STAY")
    return "ok"


class _MockResponse:
    def __init__(self, payload: dict): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def _mock_post(url, json=None, stream=False, timeout=None, **kw):
    body = json or {}
    sys_p  = (body.get("messages") or [{}])[0].get("content", "")
    user_p = (body.get("messages") or [{},{}])[1].get("content", "") if len(body.get("messages", [])) > 1 else ""
    content = _route_mock(sys_p, user_p)
    if stream:
        class _S:
            def __enter__(self_): return self_
            def __exit__(self_, *a): pass
            def raise_for_status(self_): pass
            def iter_lines(self_):
                import json as _j
                yield _j.dumps({"message": {"content": content}, "done": True}).encode()
        return _S()
    return _MockResponse({"message": {"content": content}})


main.requests.post = _mock_post  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
client = TestClient(main.app)


def assert_eq(label, got, expected):
    if got != expected:
        print(f"  FAIL  {label}: expected {expected!r}, got {got!r}")
        return False
    return True


def test_1_work_endpoint():
    print("\n[Test 1] POST /api/work → blueprint round-trip")
    res = client.post("/api/work", json={
        "teacher":  {"name": "Marlow", "role": "Inspektorin", "personality": "trocken", "traits": ["Strict"]},
        "lesson":   {"topic": "Photosynthese", "mode": "Murder", "language": "German",
                     "length": "30 min — standard", "difficulty": 0.7,
                     "school_type": "Gymnasium", "grade": "Klasse 9"},
        "material": "",
    })
    assert res.status_code == 200, res.text
    bp = res.json()
    ok = True
    ok &= assert_eq("session_id",       bp["session_id"],                       "treibhaus3-2026")
    ok &= assert_eq("phase count",      len(bp["phases"]),                      5)
    ok &= assert_eq("move count",       len(bp["moves"]),                       6)
    ok &= assert_eq("character count",  len(bp["characters"]),                  3)
    ok &= assert_eq("error trap moves", sum(1 for m in bp["moves"] if m["is_error_trap"]), 1)
    ok &= assert_eq("opening move id",  bp["opening"]["opening_move_id"],       "m01_szene")
    # No leakage of internal indexes
    ok &= "_move_index" not in bp and "_char_index" not in bp
    print("  PASS" if ok else "  FAIL")
    return ok


def test_2_work_stream():
    print("\n[Test 2] POST /api/work/stream → SSE three-stage envelope")
    with client.stream("POST", "/api/work/stream", json={
        "teacher": {"name": "Marlow", "role": "Inspektorin", "personality": "trocken", "traits": []},
        "lesson":  {"topic": "Photosynthese", "mode": "Murder", "language": "German",
                    "length": "30 min — standard", "difficulty": 0.7,
                    "school_type": "Gymnasium", "grade": "Klasse 9"},
        "material": "",
    }) as r:
        events = []
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    types = [e.get("type") for e in events]
    ok = True
    ok &= assert_eq("progress events", types.count("progress"), 3)
    ok &= assert_eq("stage_done events", types.count("stage_done"), 3)
    ok &= assert_eq("final complete event", types[-1], "complete")
    ok &= "blueprint" in events[-1]
    print("  PASS" if ok else "  FAIL")
    return ok


def test_3_chat_endpoint():
    print("\n[Test 3] POST /api/chat → structured reply + state tracking")
    res = client.post("/api/chat", json={
        "session_id": "treibhaus3-2026",
        "message":    "Der CO₂-Sensor ist hochgegangen, aber das Datenkabel ist gezogen — Manipulation.",
        "history":    [],
    })
    assert res.status_code == 200, res.text
    body = res.json()
    ok = True
    ok &= "reply" in body and "[NARRATION]" in body["reply"]
    ok &= "[NPC:" in body["reply"] and "[QUESTION]" in body["reply"]
    ok &= "[STATE]" not in body["reply"]  # backend strips [STATE]
    ok &= "phase_index" in body
    ok &= "closed" in body and body["closed"] is False
    print("  PASS" if ok else f"  FAIL — body keys: {list(body.keys())}")
    return ok


def test_4_characters_endpoint():
    print("\n[Test 4] GET /api/session/{id}/characters → NPC list")
    res = client.get("/api/session/treibhaus3-2026/characters")
    assert res.status_code == 200, res.text
    cs = res.json()["characters"]
    ok = True
    names = sorted(c["name"] for c in cs)
    ok &= assert_eq("character count", len(cs), 3)
    ok &= assert_eq("character names", names, ["Dr. Margit Riewald", "Hauke Pomrenke", "Vera Sandhoff"])
    print("  PASS" if ok else "  FAIL")
    return ok


def test_5_interrogation_endpoint():
    print("\n[Test 5] POST /api/interrogate → in-character reply, no section tags")
    res = client.post("/api/interrogate", json={
        "session_id":   "treibhaus3-2026",
        "character_id": "ch_pomrenke",
        "message":      "Warum haben Sie die UV-Lampen durch IR ersetzt?",
        "history":      [],
    })
    assert res.status_code == 200, res.text
    body = res.json()
    ok = True
    ok &= isinstance(body.get("reply"), str) and bool(body["reply"].strip())
    ok &= not re.search(r"\[(NARRATION|NPC:[^\]]+|QUESTION|STATE)\]", body["reply"])
    ok &= body["character"]["name"] == "Hauke Pomrenke"
    # Also try resolution by name
    res2 = client.post("/api/interrogate", json={
        "session_id":   "treibhaus3-2026",
        "character_id": "Hauke Pomrenke",  # by name
        "message":      "Erneut bitte.",
        "history":      [{"role": "user", "content": "vorher"}],
    })
    ok &= res2.status_code == 200
    print("  PASS" if ok else f"  FAIL — reply: {body.get('reply')!r}")
    return ok


def test_6_blueprint_parser_robustness():
    """The model output may contain stray junk; from_llm_response must be tolerant."""
    print("\n[Test 6] SessionBlueprint.from_llm_response — tolerant parsing")
    raw = "Hier kommt das Blueprint:\n\n" + _murder_photosynthese_blueprint() + "\n\nEnde."
    bp = main.SessionBlueprint.from_llm_response(raw)
    ok = True
    ok &= assert_eq("session_id", bp.session_id, "treibhaus3-2026")
    ok &= assert_eq("phase count", len(bp.phases), 5)
    ok &= assert_eq("move count", len(bp.moves), 6)
    ok &= bp.get_character("ch_riewald").name == "Dr. Margit Riewald"
    ok &= bp.get_opening_move().id == "m01_szene"
    # to_dict should not include private indexes
    d = bp.to_dict()
    ok &= "_move_index" not in d and "_char_index" not in d
    print("  PASS" if ok else "  FAIL")
    return ok


def test_7_chat_parse_sections_browser_logic():
    """Verify the regex used in chat.js parseSections behaves correctly on a realistic teacher reply."""
    print("\n[Test 7] chat.js parseSections() — Python mirror")
    reply = (
        "[NARRATION] Das Notlicht flackert. Der CO₂-Sensor ist rot, das Kabel hängt lose.\n\n"
        "[NPC:Inspektorin Marlow] „Was sehen Sie?\"\n\n"
        "[QUESTION] Was passt nicht?\n\n"
        "[STATE] STAY"
    )
    # mirror of parseSections
    stateIdx = reply.find("[STATE]")
    visible = reply[:stateIdx] if stateIdx >= 0 else reply
    tags = list(re.finditer(r"\[(NARRATION|QUESTION|NPC:[^\]]+)\]", visible))
    sections = []
    for i, m in enumerate(tags):
        end = tags[i + 1].start() if i + 1 < len(tags) else len(visible)
        content = visible[m.end():end].strip()
        tag = m.group(1).upper()
        if tag == "NARRATION": sections.append(("narration", None, content))
        elif tag == "QUESTION": sections.append(("question", None, content))
        elif tag.startswith("NPC:"):
            sections.append(("npc", m.group(1)[4:].strip(), content))
    ok = True
    ok &= assert_eq("section count", len(sections), 3)
    ok &= assert_eq("section types", [s[0] for s in sections], ["narration", "npc", "question"])
    ok &= assert_eq("npc name", sections[1][1], "Inspektorin Marlow")
    print("  PASS" if ok else "  FAIL")
    return ok


def test_8_close_session_flow():
    """Final move + ADVANCE should close the session."""
    print("\n[Test 8] Closing-move flow → session marked closed")
    sid = "treibhaus3-2026"
    # Move state forward to the closing move.
    state = main._session_state[sid]
    state["current_move_id"] = "m06_closing"
    state["turn_count"] = 6
    state["correct_count"] = 6

    # Patch the teacher reply for this test to use CLOSE.
    original = main.ask_ollama
    def patched(system_prompt, user_message, options=None, images=None):
        if "game master" in (system_prompt or ""):
            return ("[NARRATION] Marlow nickt knapp.\n\n"
                    "[NPC:Inspektorin Marlow] „Verstanden.\"\n\n"
                    "[QUESTION] —\n\n"
                    "[STATE] CLOSE")
        return original(system_prompt, user_message, options, images)
    main.ask_ollama = patched

    try:
        res = client.post("/api/chat", json={
            "session_id": sid,
            "message":    "Riewald via Pomrenke; PAR→IR; CO₂-Anreicherung; Tod durch Erstickung am Morgen.",
            "history":    [],
        })
        body = res.json()
        ok = True
        ok &= res.status_code == 200
        ok &= body["closed"] is True
        ok &= "closing_line" in body
        print("  PASS" if ok else f"  FAIL — body: {body}")
        return ok
    finally:
        main.ask_ollama = original


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = []
    for fn in [
        test_1_work_endpoint,
        test_2_work_stream,
        test_3_chat_endpoint,
        test_4_characters_endpoint,
        test_5_interrogation_endpoint,
        test_6_blueprint_parser_robustness,
        test_7_chat_parse_sections_browser_logic,
        test_8_close_session_flow,
    ]:
        try:
            results.append(fn())
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append(False)
    passed = sum(1 for r in results if r)
    print(f"\n=== {passed}/{len(results)} tests passed ===")
    sys.exit(0 if passed == len(results) else 1)
