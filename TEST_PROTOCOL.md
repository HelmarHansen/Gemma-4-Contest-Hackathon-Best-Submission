# MindHeist — Protokoll für 5 echte Qualitäts-Testläufe

## Vorbereitung

```bash
ollama pull gemma4          # oder wie auch immer das Modell bei dir heißt
pip install fastapi uvicorn requests
python -m uvicorn main:app --reload --port 8000
# Browser: http://localhost:8000
```

---

## Was bei jedem Run zu beobachten und notieren ist

### Checkpoint A — Blueprint-Generierung
- [ ] Kein 422-Fehler auf /api/work
- [ ] Blueprint enthält `planned_moves` mit ≥ 5 Moves
- [ ] Mindestens 1 Move mit `is_error_trap: true`
- [ ] Kein Move hat leeres `content`-Feld
- [ ] `opening.first_line` enthält eine konkrete Anomalie (keine Topic-Ankündigung)
- [ ] Alle `if_correct`/`if_incorrect` zeigen auf existierende Move-IDs

### Checkpoint B — Opener-Narration (erstes Chat-Event)
- [ ] [NARRATION] ist dritte Person, kein "Ich"/"Du"
- [ ] Mindestens 1 konkreter benannter Clue (kein "etwas Seltsames")
- [ ] [NPC:Name] stimmt EXAKT mit einem Charakter aus `characters` überein
- [ ] [QUESTION] ist eine Fallermittlungs-Frage, keine Schulfrage
- [ ] [STATE] ist vorhanden (STAY für die Opener-Nachricht korrekt)

### Checkpoint C — Antwort auswerten (2–3 Turns)

**Turn mit richtiger Antwort:**
- [ ] NPC beginnt NICHT mit "Genau", "Richtig", "Korrekt", "Gut", "Stimmt"
- [ ] [STATE] = ADVANCE
- [ ] Neue Szene/Clue erscheint, kein Konzept-Name im [NARRATION]

**Turn mit falscher Antwort:**
- [ ] NPC nennt BEIDE Terme: den falschen UND den richtigen, in einem Satz mit Unterschied
- [ ] [STATE] = STAY
- [ ] Narration zeigt Konsequenz (Zeuge wird abweisender etc.) statt generischem Feedback

**Hint-Button:**
- [ ] Click → [STATE] = STAY (kein Fortschritt)
- [ ] NPC gibt Hinweis aus dem `hint`-Feld des aktiven Move

### Checkpoint D — Error Trap Move
- [ ] Ein Move hat in `content` eine **spezifische falsche Aussage** (Datum, Wert, Begriff)
- [ ] Die Frage verlangt, den Fehler zu identifizieren UND zu korrigieren
- [ ] Bei korrekter Fehlernennung: ADVANCE
- [ ] Bei unvollständiger Nennung (nur "das stimmt nicht"): STAY

### Checkpoint E — Interrogation Tab
- [ ] Tab-Wechsel funktioniert, Charakterliste lädt
- [ ] Jeder Charakter hat separate Gesprächs-Historie
- [ ] Antworten sind erste Person, plain prose (kein [NARRATION], kein [STATE])
- [ ] Charakter bleibt bei seinen Wissens-/Geheimnis-Grenzen
- [ ] Bei direkter Frage zu einem Geheimnis: kürzer, defensiver Ton

### Checkpoint F — Finale Szene (CLOSE)
- [ ] Letzter Move hat `type: "closing"`
- [ ] Bei korrekter Antwort: [STATE] = CLOSE
- [ ] `closing_line` erscheint (Erfolg/Teilweise/Misserfolg je nach accuracy_ratio)

---

## Lauf 1 — Standardfall "Photosynthese" (Deutsch, Gymnasium Kl.9, Murder)

**Setup:** Topic = "Photosynthese", Sprache = Deutsch, Schwierigkeit = 0.7

**Erwartetes Blueprint-Konzept:** PAR-Licht → Photosystem II → O₂-Produktion, Stomata-Regulation

**Testschritte:**
1. Blueprint generieren, alle Checkpoint-A-Punkte prüfen
2. Opener lesen → Checkpoint B
3. Falsche Antwort geben: `"Das UV-Licht hat die Photosynthese gestoppt"` → erwartet STAY + NPC nennt "PAR, nicht UV"
4. Richtige Antwort: `"Die Strahler emittieren 850-940nm — das ist Infrarot. Photosystem II braucht PAR zwischen 400-700nm, kein IR kann die Lichtreaktion antreiben. Ohne PAR schließen die Stomata auch."` → erwartet ADVANCE
5. Error-Trap-Move finden und aktivieren (Notiz "Stomata bleiben unter IR geöffnet") → Fehler benennen
6. Interrogation: Techniker fragen "Warum wurden die Lampen getauscht?" → defensive Antwort erwartet

**Was dokumentieren:** Gibt es fabricierte Werte (z.B. Temperaturen, die nicht im Blueprint stehen)?

---

## Lauf 2 — Geisteswissenschaft "Gedichtsanalyse S&D vs. Klassik" (Deutsch, Oberstufe)

**Setup:** Topic = "Sturm und Drang vs. Weimarer Klassik — Gedichtsanalyse", Sprache = Deutsch, Schwierigkeit = 0.8

**Testschritte:**
1. Blueprint generieren → enthält es zwei datierte Manuskripte als Clues?
2. Opener: enthält er eine erste Zeile eines Gedichts zur Skansion?
3. Falsche Antwort: `"Das Manuskript 2 ist älter wegen des antiken Stoffs"` → erwartet STAY + NPC: "antiker Stoff ist kein Epochenmarker — Datum und Metrum entscheiden"
4. Richtige Antwort: Jambus, Hypotaxe, Maß-Vokabular benennen → erwartet ADVANCE
5. Gibt es einen Error-Trap mit falscher Epochenzuordnung (z.B. "Prometheus = Klassik")? → Korrektur auf S&D testen

**Was dokumentieren:** Verwendet der GM Begriffe wie "Jambus", "Parataxe" korrekt und konsistent?

---

## Lauf 3 — Andere Sprache "Biology (Cellular Respiration)" (English, University)

**Setup:** Topic = "Cellular Respiration", Sprache = English, Schwierigkeit = 0.9, Grade = "1st year university"

**Testschritte:**
1. Blueprint generieren → Mind: englische Narration
2. Alle Narration-Sections in Englisch? → falls Deutsch: Sprachfehler dokumentieren
3. Falsche Antwort: `"The ATP flatline means photosynthesis stopped"` → erwartet: NPC nennt "respiration, not photosynthesis"
4. Testen ob Schwierigkeit erkennbar höher als Lauf 1 (Subbegriffe wie "substrate-level phosphorylation", "electron transport chain")
5. Interrogation auf Englisch: spricht der Charakter Englisch?

**Was dokumentieren:** Wechselt das Modell irgendwo ins Deutsche?

---

## Lauf 4 — Kurze Session "Mathematik Statistik" (Deutsch, Realschule Kl.10, 15 min)

**Setup:** Topic = "Mittelwert, Median, Modus", Sprache = Deutsch, Länge = "15 min — quick drill", Schwierigkeit = 0.5

**Testschritte:**
1. Blueprint generieren → nur 10-12 Moves erwartet
2. Opener deutlich weniger komplex als Lauf 1/2?
3. Error-Trap muss "Mittelwert = Median" als Fehler enthalten
4. Falsche Antwort: `"Der Mittelwert liegt bei 47"` wenn eigentlich Median gemeint → STAY erwartet
5. Session bis zum Ende spielen (sollte in ~10 Turns machbar sein)

**Was dokumentieren:** Wird nach dem letzten Move korrekt CLOSE ausgegeben und `closing_line` im UI angezeigt?

---

## Lauf 5 — Cold Case mit eigenem Material

**Setup:** Topic = beliebig, Mode = "Cold Case", Material = kurzen Text einfügen (z.B. einen Auszug aus einem Biologiebuch oder einer Gedichtinterpretation)

**Testschritte:**
1. Blueprint generieren → werden Fakten AUS DEM MATERIAL verwendet? (kein Erfinden)
2. Prüfen: gibt es `source_ref`-Einträge in den Moves, die auf das Material verweisen?
3. Ein Fact prüfen: steht er wirklich im Material oder hat das Modell etwas erfunden?
4. Interrogation: kennt ein Charakter etwas, das nicht im Material steht? → Halluzination-Check

**Was dokumentieren:** Wie viele der `expected_student_response`-Einträge sind aus dem Material ableitbar?

---

## Iterationsprotokoll

Nach jedem Lauf: notiere hier Probleme und die angepasste Datei.

| Lauf | Problem | Betroffene Datei | Fix |
|------|---------|-----------------|-----|
| 1    |         |                 |     |
| 2    |         |                 |     |
| 3    |         |                 |     |
| 4    |         |                 |     |
| 5    |         |                 |     |

### Häufige Probleme und wie sie zu fixen sind:

**GM nennt Konzept direkt im [NARRATION]:**
→ `teacher_system_prompt.txt` RULE 1 Abschnitt — füge ein weiteres WRONG-Beispiel für das konkrete Thema hinzu.

**NPC bestätigt mit "Genau" / "Richtig":**
→ `teacher_system_prompt.txt` FORBIDDEN openers-Liste erweitern.

**Fabricierte Werte (Temperaturen/Daten die nicht im Blueprint stehen):**
→ `teacher_user_prompt.txt` STEP 2c schärfen — explizit: "If not in blueprint.topic_research: DO NOT STATE IT."

**Sprache wechselt:**
→ `teacher_system_prompt.txt` LANGUAGE-Regel an den Anfang verschieben, fett markieren.

**Error Trap nicht erkannt / ADVANCE ohne Fehlerkorrektur:**
→ `teacher_user_prompt.txt` STEP 1 ergänzen: "If the ACTIVE MOVE has is_error_trap: true, ADVANCE requires BOTH identifying the error AND stating the correction_key."

**Interrogation gibt [NARRATION]-Tags aus:**
→ `interrogation_system_prompt.txt` RULE 6 — das Fix ist bereits implementiert (`re.sub` in main.py). Prüfe ob es noch vorkommt.

**Blueprint zu kurz / Moves fehlen:**
→ Token-Budget in `main.py` `_OPTS_BLUEPRINT["num_predict"]` von 12288 auf 16384 erhöhen.

**JSON-Parse-Fehler beim Blueprint:**
→ Liegt meist an einfachen Anführungszeichen in Zitaten. Im `from_llm_response` ist bereits ein Repair-Mechanismus. Falls dieser auch scheitert: prüfe ob das Modell Markdown-Fences (```json) ausgibt — die werden durch `re.search(r"\{.*\}", raw, re.DOTALL)` herausgefiltert, das sollte funktionieren.
