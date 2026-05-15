# MindHeist — Worked Example Cases (Author Reasoning)

This document records the reasoning behind two fully designed reference cases used
to anchor the system prompts (`setup_prompt.txt`, `task_design_prompt.txt`,
`teacher_system_prompt.txt`). Each example is reasoned end-to-end so that the
LLM, when shown excerpts, has a concrete template for the "encode-do-not-state"
rule, error traps, causal chains, and NPC consistency.

The two cases were chosen to demonstrate range:

1. **Mordfall — Photosynthese** (natural science, mechanism-driven crime).
2. **Mordfall — Gedichtsanalyse: Sturm und Drang vs. Klassik** (humanities,
   stylistic-evidence crime).

Each case obeys the seven CHECKS in `setup_prompt.txt` and provides a model the
generator can pattern-match against.

---

## Author Reasoning — Common Method

For both cases the design process was:

1. **List the testable concepts** from the curriculum.
2. **Pick the mechanism that makes the crime impossible to solve without those
   concepts.** Knowing the topic must change *who*, *how*, or *when*.
3. **Cast NPCs as knowledge domains.** Each major suspect embodies one cluster
   of curriculum knowledge; breaking their alibi is demonstrating that knowledge.
4. **Encode every concept as physical evidence**, never as a question or
   explanation. The detective sees an anomaly; the student names the mechanism.
5. **Plant one error trap** — a deliberately wrong fact in a document/log/NPC
   line that only a student who knows the curriculum can correct.
6. **Verify the causal chain**: each move's expected answer must be unlocked by
   the previous move's content, not by general knowledge.

This file documents the result. The pedagogically load-bearing fragments are
mirrored as inline examples in the prompts.

---

## Case 1 — "Treibhaus 3" (Topic: Photosynthese, Klasse 9, Gymnasium, 0.7)

### Step 1 — Testable concepts

- Photosynthese-Lichtreaktion benötigt PAR-Wellenlängen (Photosystem II
  absorbiert maximal bei ca. 680 nm; Chlorophyll-a/b-Absorption bei ca. 430
  und 660–680 nm). Infrarot kann Photosystem II nicht antreiben.
- Stomata öffnen unter sichtbarem Licht; im Dunkeln (oder bei reinem IR)
  schließen sie → kein Gasaustausch.
- 6 CO₂ + 6 H₂O → C₆H₁₂O₆ + 6 O₂ (Bilanz der Lichtreaktion + Calvin-Zyklus).
- Photosynthese stoppt deutlich oberhalb ~40 °C (Enzymdenaturierung).
- Pflanzen sind grün, weil Chlorophyll grünes Licht (ca. 500–565 nm)
  reflektiert.

### Step 2 — Crime mechanism

Ein versiegeltes Gewächshaus, in dem der Botaniker Dr. Falk Brendler tot
aufgefunden wird. Todesursache: CO₂-Anreicherung über Nacht. Der Mechanismus
ist **physikalisch nur erklärbar, wenn man Photosynthese verstanden hat**:

1. UV/PAR-Pflanzenlampen wurden gegen Infrarotlampen ausgetauscht.
2. CO₂-Düngung blieb angeschlossen.
3. Ohne PAR-Licht keine Lichtreaktion → keine O₂-Freisetzung; gleichzeitig
   schließen sich die Stomata, sodass die Pflanzen das eingespeiste CO₂ auch
   nicht aufnehmen.
4. CO₂ reichert sich über Nacht an; O₂-Anteil sinkt.
5. Brendler betritt am Morgen die versiegelte Kammer und erstickt.

> "How does understanding Photosynthese change who could have done this?" —
> Nur jemand, der weiß, dass IR Photosystem II nicht anregt und Stomata bei
> Dunkelheit schließen, kann diesen Tod inszenieren. Klassisches
> Topic-Causal-Crime-Pattern.

### Step 3 — NPCs as knowledge domains

- **Dr. Margit Riewald** (Co-Forscherin) — kennt das gesamte
  Photosystem-Setup. Motiv: Streit um Autorenschaft. **Wissensdomäne:
  Lichtreaktion / Photosystem II / Wellenlängen.** Geheimnis: Sie war in der
  Tatnacht im Gewächshaus.
- **Hauke Pomrenke** (Techniker) — hat den Lampentausch dokumentiert.
  **Wissensdomäne: Lampenspektrum (UV / PAR / IR), Wartungslog.** Geheimnis:
  Wurde bezahlt.
- **Vera Sandhoff** (Sicherheitschefin) — Magnetkarten-Log.
  **Wissensdomäne: CO₂-Düngung in der Forschung.** Geheimnis: kennt
  CO₂-Toxizitätswerte aus eigenem Projekt.

### Step 4 — Encoded evidence (NEVER stated)

| Konzept | Falsch (stated) | Richtig (encoded) |
|---|---|---|
| Photosystem II braucht 680 nm | "Die Lampen liefern nicht die richtige Wellenlänge für Photosynthese." | "Die ausgetauschten Strahler emittieren laut Typenschild 850–940 nm. Der Pflanzensensor an Tisch 3 zeigt seit 23:48 Uhr keinen O₂-Anstieg mehr." |
| Stomata schließen ohne PAR | "Die Stomata waren geschlossen." | "Mikroskopische Aufnahmen der unteren Blattepidermis zeigen die Schließzellen geschlossen — trotz CO₂-Überangebot in der Kammer." |
| Chlorophyll grün durch Reflexion | "Pflanzen sehen grün aus, weil sie grünes Licht reflektieren." | "Unter den Infrarotstrahlern wirken die Blätter dunkel-grau; das Photometer zeigt im 530-nm-Band keine Reflexion mehr — die Lampen liefern diesen Bereich nicht." |

### Step 5 — Error trap (CHECK 7)

- Move `m03_zettel` — auf Riewalds Tisch ein Notizzettel: "Brendler wollte
  Stomata-Verhalten unter IR testen. Mit reiner IR-Beleuchtung bleiben die
  Stomata geöffnet → CO₂-Aufnahme möglich."
- `is_error_trap: true`
- Der Fehler: Stomata öffnen unter **PAR-Licht**, nicht unter IR. Unter
  reiner IR-Beleuchtung schließen sie, **keine** CO₂-Aufnahme.
- `error_correction_key`: "Stomata öffnen unter PAR (ca. 400–700 nm), nicht
  unter Infrarot — sie schließen unter IR-only."
- `hint`: "Im Kapitel Lichtreaktion: Stomata-Regulation."
- `source_ref`: "Biologie Kl. 9 / 10: Photosynthese — Lichtreaktion und
  Stomata-Regulation."

### Step 6 — Causal chain (CHECK 6)

`m01_szene` zeigt CO₂-Sensor rot + Datenkabel abgezogen → `m02_pomrenke`
fragt nach Wellenlänge der neuen Lampen (Antwort braucht m01) →
`m03_zettel` (Fehlerfalle Stomata) → `m04_dueger` CO₂-Düngung (Bilanz
braucht m03) → `m05_sandhoff` (Karten-Log widerspricht Riewalds Alibi) →
`m06_chlorophyll` (warum Pflanzen unter IR keine O₂ produzieren) →
`m07_closing` (vollständiger Tathergang).

### Step 7 — Closing move

Der Detektiv muss dem Untersuchungsrichter erklären: **wer** (Riewald als
Motiv-Trägerin, Pomrenke als Werkzeug), **wie** (PAR → IR + offene
CO₂-Düngung + versiegelte Kammer = CO₂-Anreicherung mangels Lichtreaktion
**und** mangels Stomata-Aufnahme), **womit** (Lampen + CO₂-Flasche), **warum**
(Autorenschaftsstreit). Ohne Verständnis von Photosystem II,
Stomata-Regulation und Stoffbilanz ist diese Erklärung unmöglich.

---

## Case 2 — "Lex & Faun" (Topic: Gedichtsanalyse — Sturm und Drang vs. Klassik, Oberstufe, 0.85)

Humanities cases sind ungleich heikler: die "Beweise" sind sprachliche Eigenschaften,
nicht Messwerte. Der Schlüssel: aus Stil und Form selbst Belege machen.

### Step 1 — Testable concepts

- **Sturm und Drang (≈ 1765–1785):** parataktischer Stil, freie Rhythmen,
  emotive Naturmetaphorik, Apostrophen an Gottheiten, dynamische Verben,
  rebellisches Genie-Motiv (z. B. Goethe, "Prometheus", 1774).
- **Weimarer Klassik (≈ 1786–1805):** Hypotaxe, geregelte Versmaße
  (insbes. Blankvers / fünfhebiger Jambus), Antikenbezug, Maß-, Humanitäts-
  und Vernunftideal (z. B. Goethe, "Iphigenie auf Tauris", 1787).
- **Stilmittel:** Apostrophe, Anapher, Inversion, Enjambement, Personifikation,
  Hyperbel, Metapher.
- **Versmaß:** Jambus (u−), Trochäus (−u), freie Rhythmen.
- **Lyrisches Ich ≠ Verfasser.**
- **Parataxe ≠ Hypotaxe.**

### Step 2 — Crime mechanism

Im Antiquariat "Lex & Faun" wird der Inhaber Albrecht Knoll erschlagen
aufgefunden. Auf dem Schreibtisch zwei Manuskripte, beide als
"Goethe, 1774, Autograph" deklariert. Knoll wollte am nächsten Morgen die
Echtheit prüfen — und wurde deshalb ermordet.

**Das eine Manuskript ist echt (Sturm-und-Drang-Hymne, freie Rhythmen,
parataktisch). Das andere ist eine Fälschung — stilistisch verraten durch
klassizistische Merkmale, die 1774 noch nicht zu Goethe gehörten.**

> "How does understanding Gedichtsanalyse change who could have done this?" —
> Nur wer Sturm und Drang vs. Klassik stilistisch unterscheiden kann, kann
> die Fälschung identifizieren und damit das Motiv des Mörders rekonstruieren.

### Step 3 — NPCs as knowledge domains

- **Dr. Reto Kennelbach** (Literaturhistoriker, "Echtheitsexperte") —
  **Wissensdomäne: Epochenmerkmale**. Hat das Echtheitszertifikat
  ausgestellt. Geheimnis: Wurde bezahlt; das Zertifikat ist sachlich falsch.
- **Iva Kremling** (Restauratorin) — **Wissensdomäne: Versmaß, Tinten und
  Schriftbild**. Geheimnis: Sie hat die Fälschung selbst geschrieben — eine
  exzellente Lyrik-Kennerin, aber bei der Imitation des S&D-Duktus
  durchgerutscht.
- **Hadrian Vossberg** (Käufer) — **Wissensdomäne: Markt und Provenienz**.
  Geheimnis: Ahnte die Fälschung; wollte sie öffentlich machen.

### Step 4 — Encoded evidence

| Konzept | Falsch (stated) | Richtig (encoded) |
|---|---|---|
| Apostrophe als S&D-Marker | "Das Gedicht hat eine Apostrophe — typisch S&D." | "Die erste Zeile lautet 'Bedecke deinen Himmel, Zeus, mit Wolkendunst!' — direkte Anrede an die Gottheit, Imperativ, exklamatorisch." |
| Parataxe vs. Hypotaxe | "Im S&D dominiert die Parataxe." | "Im zweiten Manuskript beginnt die zweite Strophe mit: 'Heilig sind mir die Götter, doch ich diene nicht ihrer Macht, wenn das Maß mich nicht zur Mäßigung ruft.' — drei Nebensatzkonstruktionen, ein Konditional, eine Konzessivkonstruktion." |
| Versmaß: freie Rhythmen vs. Blankvers | "Prometheus ist in freien Rhythmen." | "Manuskript 2 lässt sich durchgängig als −u−u−u−u−u skandieren — fünfhebiger Jambus, sauber regelmäßig, ohne ein einziges überzähliges Hebungssilbe." |
| Vokabular: Genie vs. Maß | "Klassik betont das Maß." | "Auffällig: Begriffe wie 'Mäßigung', 'Humanität', 'edler Sinn' tauchen in M2 wiederholt auf — in M1 dagegen 'Glut', 'donnernd', 'Schmerz', 'Trotz'." |

### Step 5 — Error trap (CHECK 7)

- Move `m04_zertifikat` — Kennelbachs Echtheitszertifikat behauptet:
  "Goethes Prometheus (1774): klassischer Goethe-Stil, fünfhebiger Jambus,
  Antikenbezug."
- `is_error_trap: true`
- Der Fehler verkettet drei sachliche Irrtümer:
  1. 1774 ≠ Klassik; Goethe war in der Sturm-und-Drang-Phase.
  2. "Prometheus" ist nicht im fünfhebigen Jambus, sondern in **freien
     Rhythmen** geschrieben.
  3. Antikenbezug allein macht kein Gedicht "klassisch" — der Stoff ist
     antik, die Behandlung im S&D rebellisch.
- `error_correction_key`: "Prometheus (1774) = Sturm und Drang, freie
  Rhythmen, rebellische Apostrophe — nicht Klassik, nicht Blankvers."
- `hint`: "Phasenchronologie Goethe; Hymnenform 1772–1774."
- `source_ref`: "Deutsch Oberstufe: Goethes Lyrik 1772–1775 vs. Iphigenie
  1786/87."

### Step 6 — Causal chain

`m01_szene` (zwei Manuskripte, eines davon Fälschung — was unterscheidet
sie?) → `m02_kennelbach` (Datierung 1774 = welche Phase?) →
`m03_apostrophe_in_m1` (echte S&D-Hymne in m1 erkennen) →
`m04_zertifikat` (Fehlerfalle: Kennelbachs Zertifikat) →
`m05_metrum` (Skansion von m2 = fünfhebiger Jambus → klassisch, nicht S&D)
→ `m06_parataxe` (Satzbau m2 hypotaktisch → klassisch) → `m07_closing`
(Fälschungsnachweis und Tathergang).

### Step 7 — Closing move

Der Detektiv weist die Fälschung an drei stilistischen Befunden nach:
**Versmaß** (fünfhebiger Jambus statt freier Rhythmen), **Syntax**
(Hypotaxe statt Parataxe), **Lexik** (Maß-Vokabular statt Genie-Pathos).
Daraus folgt: Kremling ist die Fälscherin, Kennelbach der Mitwisser,
Vossberg das Opfer der nächsten geplanten Täuschung. Knolls Mord wurde
notwendig, weil seine Echtheitsprüfung diese drei Befunde am nächsten Tag
ans Licht gebracht hätte.

---

## What this changes in the prompts

The two cases above are condensed into examples inside the prompt files so
that the generator has a concrete model — not just rules — for:

1. **Encoding evidence instead of stating the concept**
   (`setup_prompt.txt` → MOVE CONTENT EXAMPLES section is extended with one
   physics-style and one humanities-style example.)
2. **Error traps in humanities** — the example "Goethe-Echtheitszertifikat"
   is added so that the generator does not assume error traps are only
   numeric.
3. **NPCs as knowledge domains** — each prompt is updated so the
   generator must explicitly assign one knowledge cluster per major NPC,
   illustrated with both Riewald (Photosystem II) and Kennelbach
   (Epochenmerkmale).
4. **Causal chain** — the prompts now show a 7-move chain for both science
   and humanities so that the generator does not collapse humanities cases
   into vague "interpretation" tasks.
5. **Closing move** — both example closings demand multi-component answers
   (who + how + why + corroborating mechanism), which the prompts now state
   explicitly as the closing-move shape.

Token budgets in `main.py` were also raised across the three stages so that
none of these worked examples get truncated when the model echoes them
back as part of its own blueprint.
