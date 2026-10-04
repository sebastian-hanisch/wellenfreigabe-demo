# Kommissionierwellen: Fristen und Gangblockaden – Streamlit-Demo

*(noch nicht deployed)*

Interaktive Fall-Demo (Lager-Linie): Kommissionierer arbeiten vorgebildete **Batches** mit **Versandfristen** ab und laufen dabei durch schmale Gänge, in denen sie sich **nicht überholen** können – jeder Gang ist eine
Einzelressource mit FIFO-Warteschlange am Eingang. Die Demo beantwortet: **Wie viel kostet das Blockieren, wie viel vom Vorteil einer Fristenregel bleibt dann übrig – und wann lohnt es sich, Gangkonflikte gezielt zu
vermeiden, obwohl man dafür dringende Batches zurückstellt?**

Teil des Portfolios für die Website „Sebastian Hanisch – Operations Research und Machine Learning". **Erweiterung der Batching-Demo** (`order_batch-demo`, „baut aus"): sie hebt zwei stillschweigende Annahmen dort
auf – dass Batches ohne Fristen bearbeitet werden und dass gleichzeitig arbeitende Kommissionierer sich nicht behindern (vermerkt in deren „Bewusst nicht enthalten" und „Anpassungsideen"). Regeln im Vergleich:
**FIFO**, **EDD** (frühester Fristbatch zuerst), **EDD mit Konflikt-Fenster w** (Regler 1 bis 8, w = 1 ist EDD) und, nur für Kleininstanzen, das **exakte Optimum** (CP-SAT) als Maßstab.

## Warum dieses Problem

Mehr Kommissionierer bedeuten nicht proportional mehr Durchsatz: in schmalen Gängen warten sie aufeinander, und das trifft ausgerechnet die Batches mit knappen Fristen. Der ehrliche Aufhänger ist **nicht**
„eine schlaue Regel löst das Blockieren": Blockieren ist groß (selbst das exakte Optimum zahlt einen Aufpreis), es frisst einen großen Teil des Vorteils einer Fristenregel, und die einfache Konfliktvermeidung
(„EDD mit Konflikt-Fenster") hilft nur unter engen Fristen **und** auf wenige „heiße" vordere Gänge konzentrierter Dringlichkeit, sonst schadet sie. Die Hauptansicht formuliert deshalb eine **bedingte Aussage**
(Blockieren kaum relevant / Konfliktvermeidung lohnt / schadet / kein belastbarer Unterschied) statt eines Siegers.

## Modell

Parallelgang-Lager (Depot vorn links, Ganglänge 30 m, Gangabstand 3 m, 1,3 m/s, 8 s je Pickposition). N Bestellungen (je 2 bis 6 Positionen, alle zum Zeitpunkt 0 verfügbar) sind vorab nach Gangähnlichkeit zu Batches
mit höchstens 15 Positionen gebündelt – **ohne Rücksicht auf Fristen**. Route je Batch: S-Shape (aufsteigende Gänge, alternierende Richtung, jeder Gang mit Positionen wird ganz durchquert, bei ungerader Gangzahl der
letzte als Sackgasse, Ende immer am Depot). K Kommissionierer, Freigabe sofort beim Frei-Werden. Fristen relativ zur geschätzten Gesamtdauer (Fristendruck τ, kleiner = enger), Express-Bestellungen (Gewicht 3) mit
engerer Frist, Batchfrist = früheste Frist seiner Bestellungen; Ziel: **gewichtete Gesamtverspätung** in Minuten. Die **heißen Gänge** (die 3 vordersten) koppeln Dringlichkeit und Gangkonflikt; der Regler ρ ist der
Anteil der Express-Positionen, die gezielt dort gezogen werden (die übrigen folgen der allgemeinen Gangverteilung; bei ρ = 0 liegen rund 51 % trotzdem vorn). Alle Zeiten sind ganzzahlige Dezisekunden, damit Simulation und CP-SAT-Modell dieselbe Rechnung machen. Formal im Expander „📐 Mathematische Formulierung" der App.

Nach dem Modell-Register ist das ein **Job-Shop mit Fristen und Obergrenze paralleler Aufträge** (Gänge = Einzelmaschinen, Batches = Aufträge, Kommissionierer = Obergrenze). Ohne Blockieren fällt er exakt auf das
Modell der `warehouse-transfer-demo` zurück (in den Tests unabhängig nachgerechnet); die Blockier-Bedingung ist dasselbe Prinzip wie in der `quaycrane-demo` (Kräne auf einer gemeinsamen Schiene, dort
eindimensional), hier in zwei Dimensionen (Gänge als Einzelressourcen).

## Methodik – drei Regeln plus ein exakter Maßstab

- **🐌 FIFO**: Batches in Bildungsreihenfolge freigeben, ohne Fristen – die **Kontrast-Baseline**.
- **📅 EDD**: immer den Batch mit der frühesten Frist freigeben, blind dafür, wo andere Kommissionierer gerade sind – die **fristenbewusste Basisregel** und der Vergleichsmaßstab des Fensters.
- **🚧 EDD mit Konflikt-Fenster w**: unter den w dringendsten Batches den mit den wenigsten Gangkonflikten zu gerade aktiven Batches wählen (Gleichstand nach Frist), Regler w = 1 bis 8 – die **Untersuchungsregel**.
- **🎯 Exakt (CP-SAT)**: Optimum des Job-Shop-Modells für Kleininstanzen (bis 10 Batches, 30 Bestellungen), mit und ohne Blockieren; Button mit 20 s Zeitlimit je Lösung und Abkühlpause, nur für die gezeigte Einzelinstanz.

Alle Kennzahlen stehen auf **80 Instanzen** (Seeds 0 bis 79 des Reglerstands), Vergleiche sind **gepaart** je Instanz, angegeben als Mittel ± Standardfehler; ein Vorzeichen gilt nur ab 2 Standardfehlern (drei Zustände:
belastbar positiv / belastbar negativ / kein belastbarer Unterschied). Der Seed bestimmt nur die gezeigte Instanz (Gang-Belegung), einen Einzelfall.

**Kernlogik unverändert übernommen**: `wfg_scenario.py`, `wfg_sim.py` und `wfg_cp.py` stammen aus `lager-planung/messreihe_wellen_konflikt/wellen.py` – dort bereits gegen 7 Checks und die exakte Referenz
verifiziert, hier als Tests übernommen (`tests/test_core_checks.py`). Simulation und Auswertung: reine Standardbibliothek; `ortools` nur für den Exakt-Tab, beim Aufruf importiert, damit die App auch ohne Solver startet.

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen sind deterministisch und in `tests/test_claims.py` nachgerechnet (Standard-Lager: 8 Gänge, 60 Bestellungen, etwa 17 Batches, τ = 0,8, 25 % Express, ρ = 80 %; Werte in gewichteten Verspätungsminuten,
80 Instanzen).

| Frage | Befund | Test |
|---|---|---|
| Wie groß ist das Blockieren? | Wartezeitanteil (Regel EDD) wächst mit der Kommissionierer-Zahl von 4,0 % (K = 2) auf 42,1 % (K = 8); Standard (K = 4): 16,3 %, die Verspätung von EDD verdoppelt sich von 139,5 auf 279,3 | `test_claims.py::test_standard_lager_numbers_in_the_readme`, `::test_blocking_share_grows_from_four_to_forty_two_percent` |
| Frisst Blockieren den Vorteil der Fristenregel? | Ja, mit der Kommissionierer-Zahl wachsend: Vorteil von EDD gegenüber FIFO ohne → mit Blockieren: K = 3 156,1 → 147,3 (-5,6 %), K = 4 114,9 → 91,8 (-20,1 %), K = 6 66,2 → 28,2 (-57,4 %); bei K = 2 kein Unterschied (240,8 vs. 240,5) | `::test_advantage_erosion_by_pickers`, `::test_erosion_is_belastbar_from_three_pickers_on` |
| Kontrollfall: wenige Kommissionierer | K = 2: Wartezeitanteil 4,0 %, Fristenvorteil mit ≈ ohne Blockieren (240,5 vs. 240,8) – und das Fenster (w = 4) **schadet**: -11,0 ± 3,5 | `::test_few_pickers_control_case` |
| Viele Kommissionierer | K = 6: Wartezeitanteil 30,7 %, der Fristenvorteil schrumpft auf 42,6 % des Vorteils ohne Blockieren; das Fenster (w = 2) hilft hier nicht belastbar | `::test_many_pickers_case` |
| Wann lohnt Konfliktvermeidung? | Nur bei engen Fristen **und** konzentrierter Dringlichkeit: τ = 0,5, ρ = 100 %, w = 4: **+17,9 ± 5,3** Minuten (positiv = das Fenster hilft) | `::test_the_two_regimes_of_the_window` |
| Wann schadet sie? | Bei lockeren Fristen und unabhängiger Dringlichkeit: τ = 1,6, ρ = 0 %, w = 4: **-41,1 ± 3,0** Minuten – die Regel opfert Dringlichkeit für Konfliktvermeidung, die dann nichts bringt | `::test_the_two_regimes_of_the_window` |
| Wie sieht das Vorzeichenmuster im Standard-Lager aus? | Von 9 Zellen (ρ = 0/50/100 % × w = 2/4/8) hilft das Fenster in 1 belastbar (ρ = 100 %, w = 2: +10,0 ± 3,3), schadet in 2 (u. a. ρ = 0 %, w = 8: -32,4 ± 5,9), 6 ohne belastbaren Unterschied | `::test_rho_sweep_sign_pattern_in_the_standard_lager` |
| Holt das Fenster das Blockieren zurück? | Nein, nur einen Teil: Standard, w = 2: +11,9 ± 3,6 von 279,3 – die Blockade bleibt | `::test_standard_lager_numbers_in_the_readme` |
| Wie viel ist selbst bei bester Planung unvermeidbar? | **Vorab-Messung** (10 Kleininstanzen je ρ, 6 Gänge, 24 Bestellungen, K = 3, 12 s Limit je CP-Lauf, mit Blockieren jeweils 9 von 10 Läufen bewiesen optimal, `messreihe_wellen_konflikt/cp_gap.json`): das Optimum liegt 19,6 % (ρ = 0) bzw. 13,0 % (ρ = 1) unter EDD und zahlt 29,2 % bzw. 35,1 % Aufpreis fürs Blockieren gegenüber dem blockierfreien Optimum. **Nicht Teil der CI-Tests** (Löser-Läufe mit Zeitlimit) | – (Vorab-Messung) |

## Ehrliche Grenzen

- **Kein Sieger, sondern eine bedingte Aussage**: das Konflikt-Fenster holt im günstigsten Regime nur einen kleinen Teil des Blockierens zurück (Standard: 11,9 von 279,3 Minuten) und schadet in großen Teilen des
  Parameterraums. Es ist eine einfache Heuristik; eine echte blockier-bewusste Routenplanung (Besuchsreihenfolge im Batch an freie Gänge anpassen) ist nicht enthalten und könnte mehr vom Potenzial heben.
- **Stark stilisiert**: S-Shape mit ganzer Gangdurchquerung, Einzelressource Gang mit FIFO, alle Bestellungen zum Zeitpunkt 0 (keine Ankünfte über die Zeit), feste Kommissionierer-Zahl, frist-blind vorgebildete Batches.
  Konkurrierende Modelle (Mehrfachbelegung breiter Gänge, Überholen, Rückkehr-Routen) würden die Größenordnungen verschieben.
- **Nicht kalibriert**: ρ, heiße Gänge und Fristenverteilung sind synthetisch, nicht an einem echten Lager. Die Kernaussage (das Vorzeichen des Fenster-Effekts hängt von Fristendruck und Dringlichkeitskonzentration ab)
  ist robust über die getesteten Zellen, die Prozentwerte sind es nicht.
- **Exakte Referenz nur für Kleininstanzen** (bis 10 Batches, 30 Bestellungen; CP-SAT beweist bei etwa 7 bis 9 Batches, bei 17 nicht): für die Standardgröße ist das Optimum unbekannt, das Potenzial dort nur
  abschätzbar. Auch im Exakt-Tab sind nicht bewiesene Werte als Näherung gekennzeichnet (Potenzial „mindestens", Preis „höchstens" bzw. „Näherung").
- **Die gezeigte Instanz ist ein Einzelfall**: der Seed bestimmt nur das Gantt. Die Preset-Seeds liegen außerhalb der Stichprobe (Seeds 0 bis 79) und wurden so gewählt, dass Wartezeitanteil und Verspätung nahe am
  Populationsmittel des Presets liegen (`tools/tune_presets.py --seeds`).

## Verwandte Demos mit demselben mathematischen Modell

Nach dem Modell-Register ist die Kombination formal ein **Job-Shop mit Fristen und Obergrenze paralleler Aufträge** (Gänge = Einzelmaschinen, Batches = Aufträge, Kommissionierer = Obergrenze):

- **`warehouse-transfer-demo`** – dasselbe Modell **ohne Blockieren**: parallele Maschinen mit Fristen (Fristen-Disposition, Simulation, Regeln, CP-SAT). Dort behindern sich Transporter nicht; hier ist das Blockieren der Kern.
  Der Rückfall ist exakt: bei ausgeschaltetem Blockieren stimmt die Simulation mit einem unabhängig geschriebenen List-Scheduling überein (`test_core_checks.py::test_blocking_off_equals_independent_list_scheduling`).
- **`quaycrane-demo`** – **Blockieren auf gemeinsamer Bahn** (Kräne auf einer Schiene, in einer Dimension); hier dasselbe Blockier-Prinzip in zwei Dimensionen (Gänge als Einzelressourcen).
- **`order_batch-demo`** – der **Vorgänger**: dort werden die Batches gebildet (14 Metaheuristiken), ohne Fristen und ohne Blockieren. Hier stehen die Batches fest (kleine eigene Greedy-Seed-Bildung, keine Repo-Kopplung).

## Tests und Verifikation

`python -m pytest tests/ -v` – 222 Tests, rund 2 1/2 Minuten (davon etwa 110 s AppTests). Zusammensetzung:

- **Kernlogik** (`test_core_checks.py`): alle 7 Checks aus `messreihe_wellen_konflikt/check.py` – Handinstanz (Blockieren kostet exakt eine Gangdauer), K = 1 → nie Blockieren, ohne Blockieren = unabhängiges
  List-Scheduling (240 Fälle), Laufzeit = Arbeit + Wartezeit und keine Doppelbelegung, Instanz-Sanity, Fenster-Regel wird nachweislich ausgeführt, CP-Referenz (klein und mit kurzem Limit, nur Beweisbares: ein
  bewiesenes Optimum wird von keiner Heuristik unterboten) – plus CP-Handinstanzen mit exakt bekanntem Optimum (mit Blockieren 200, ohne 100, mit K = 1 seriell 200).
- **Zweige und Randfälle** (`test_branches_and_edges.py`): **jede Regel weicht auf mindestens einer Instanz von ihrer Nachbarregel ab** (FIFO ↔ EDD ↔ Fenster 2 ↔ 4 ↔ 8; Hintergrund: in der Vorab-Messung lief die
  Fenster-Regel zunächst nie, alle Differenzen waren exakt 0,00 ± 0,00 – eine Spalte aus Nullen ist ein Fehlersignal, kein Befund), Handinstanz, an der das Fenster nachweislich den konfliktärmeren Kandidaten wählt,
  Randfälle (K = 2, 4 Gänge, 20 Bestellungen, ein einziger Batch, Express 5 %, ρ = 0 und 100 %, w größer als die Zahl wartender Batches, τ an beiden Grenzen, Maximum).
- **Auswertung** (`test_evaluation.py`): gepaarte Differenz und Urteil an der 2-SE-Schwelle (künstliche Werte), die vier Meldungszustände, Population gegen Direktrechnung, **Reproduktion der Messreihe**
  (`tests/data/sweep_reference.json`: Presets, Kommissionierer-Sweep und Beispielinstanz exakt), ρ-Sweep, Exakt-Zusammenfassung.
- **Regler** (`test_presets.py`): Permalink-Parsing/-Klemmen/-Einrasten (Zehntel für τ, 5er-Schritte für ρ), Presets innerhalb ihrer Reglergrenzen und auf dem Reglerraster, Preset-Seeds außerhalb der Stichprobe.
- **Presets** (`test_stories.py`, `test_preset_stories.py`): jedes Abnahmekriterium kippt an künstlichen Werten genau an seiner Schwelle, Vorzeichen-Kriterien nur zusammen mit der Standardfehler-Bedingung; die echten
  Presets erfüllen ihre Kriterien auf den 80 Instanzen.
- **Figuren** (`test_visualization.py`): Gantt (Balken je Gangbesuch gegen das Protokoll, Wartezeit gegen die Simulation, Legende), Balkengrafiken, alle Achsen `fixedrange`.
- **PDF** (`test_pdf_export.py`): Sonderzeichen-Bereinigung (fpdf2 stürzt bei „–", „€", Emoji und dem Unicode-Minus ab – mit den genauen Zeichen getestet), jedes Preset, Reglergrenzen, Exakt-Abschnitt.
- **Aussagen** (`test_claims.py`): jede Zahl dieser README.
- **End-to-End** (`test_app.py`, AppTest): Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, kein toter Regler, alle vier Meldungszustände, Exakt-Tab (Größenpr., Button-Pfad mit Stub und
  mit kurzem echtem Limit, Cooldown, Veralten, fehlender Solver), PDF, Texte.

Zusätzlich ein Fehler-Einbau-Test (`tools/mutation_check.py`, 76 Mutanten über `wfg_scenario`, `wfg_sim`, `wfg_cp`, `wfg_evaluation`, `wfg_presets`, `wfg_stories`, `wfg_visualization`, `wfg_pdf_export`):
**76 gefunden, 0 überlebt, 0 Fehler in der Mutantenliste.** Das Werkzeug prüft sich selbst: vor dem Lauf muss eine unveränderte Kopie alle Tests bestehen (sonst Abbruch).

**Beim Bau gefundene Testlücken (per Mutationstest, dann geschlossen):** der erste Lauf meldete „76 gefunden", war aber wertlos – auch ein Mutant ohne jede Änderung „fiel durch", weil die Kopie das README nicht enthielt, das
`test_claims.py` liest. Nach der Korrektur und der Selbstprüfung überlebten vier echte Mutanten: (1) die Zählung verspäteter Bestellungen (`tard > 0` → `>= 0`) – geschlossen durch Handinstanz und unabhängiges Nachzählen;
(2) die Größenprüfung des Exakt-Tabs an der Grenze (`<=` → `<` bei 10 Batches) – geschlossen durch Grenzwert-Tests mit genau 10/11 Batches und 30/31 Bestellungen; (3) die Gewichte im CP-Ziel (`wt * t` → `t`) – geschlossen durch eine
CP-Handinstanz mit Gewicht 3 (Optimum 300 statt 200); (4) das Zurückrunden beim Einrasten des Fristendrucks (`0,4 + k × 0,1` liefert bei k = 2, 3, 8, 13, 14 Gleitkomma-Rauschen wie 0,6000000000000001) – geschlossen durch einen Test
über das ganze Zehntel-Raster.

## Dateistruktur

| Datei | Inhalt | Herkunft |
|---|---|---|
| `app.py` | Streamlit-Hauptablauf: Presets, Sidebar, Hauptansicht, Kernabschnitt, Regeln im Vergleich (inkl. Exakt-Tab), Texte | neu |
| `wfg_constants.py` | Regler-Grenzen, feste Parameter, Regeln, Farben, `PRESETS` | neu |
| `wfg_presets.py` | `SETTING_SPECS`, Permalink, Presets, Seed-Knopf | Muster `rrs_presets.py` |
| `wfg_scenario.py` | `Cfg`, Greedy-Seed-Batching, S-Shape-Route, `make_instance` | `messreihe_wellen_konflikt/wellen.py`, unverändert |
| `wfg_sim.py` | Ereignissimulation mit Gang-FIFO, Regeln FIFO/EDD/EDD-w | `wellen.py`, unverändert |
| `wfg_cp.py` | CP-SAT-Modell (`ortools` beim Aufruf importiert), Größenprüfung des Exakt-Tabs | `wellen.py`, unverändert (+ Größenprüfung) |
| `wfg_evaluation.py` | Population (80 Instanzen), gepaarte Urteile, Meldungszustände, Kommissionierer- und ρ-Sweep, Exakt-Zusammenfassung | Muster `rvm_evaluation.py` |
| `wfg_visualization.py` | Gantt der Gang-Belegung, Vorteil je Kommissionierer-Zahl, Fenster-Gewinn je ρ (alle Achsen fest) | neu |
| `wfg_ui_panel.py` | Kennzahlen (2 × 2), Meldung, Regel-Panel, Vergleichstabelle, Exakt-Ergebnis | Muster `rrs_ui_panel.py` |
| `wfg_pdf_export.py` | PDF-Export (`fpdf2`, Sonderzeichen-Bereinigung) | Muster `rrs_pdf_export.py` |
| `wfg_stories.py` | Abnahmekriterien der Presets | Muster `rrs_stories.py` |
| `tools/tune_presets.py` | Preset-Abstimmung, Suche repräsentativer Anzeige-Seeds (`--seeds`) | neu |
| `tools/mutation_check.py` | Fehler-Einbau-Test (parallel, je Mutant eine Kopie) | Muster `rrs_...`, erweitert |
| `tests/` | siehe oben | neu |

## Bewusst nicht enthalten

Die folgenden Erweiterungen sind ausdrücklich nicht Teil von Version 1 – jede würde Größenordnung und Aussage verschieben und gehört als Ausbau genannt, nicht stillschweigend eingebaut:

- **Bestellungen, die über die Zeit eintreffen** (echte Wellen statt „alles zum Zeitpunkt 0").
- **Andere Routen-Strategien** (Largest-Gap, Rückkehr-Routen) statt S-Shape mit ganzer Gangdurchquerung.
- **Blockier-bewusste Routenplanung** (Besuchsreihenfolge im Batch an freie Gänge anpassen) – könnte mehr vom Rest-Potenzial heben, das der exakte Maßstab zeigt.
- **Mehrfachbelegung breiter Gänge** (Überholen, mehrere Kommissionierer je Gang) statt Einzelressource.
- **Ungleiche Kommissionierer** (unterschiedliche Geschwindigkeit, Qualifikation, Zonen).
- **Kalibrierung an einem echten Lager** (ρ, heiße Gänge, Fristenverteilung sind synthetisch).
- **Kopplung an die Batch-Bildung der Batching-Demo**: die Batches bleiben frist-blind vorgebildet (eigene kleine Greedy-Seed-Implementierung, keine Repo-Kopplung).
- **Exakte Lösung für die Standardgröße** (etwa 17 Batches; das Optimum ist dort unbekannt).

## Lokal ausführen

```bash
pip install -r requirements-dev.txt
streamlit run app.py
```

Tests: `python -m pytest tests/ -v`. Preset-Abstimmung: `python tools/tune_presets.py [--seeds]`. Fehler-Einbau: `python tools/mutation_check.py [Modul] [--jobs N]`.

---

Gebaut mit Streamlit, Plotly, OR-Tools und fpdf2.

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Lagerlogistik optimieren](https://sebastianhanisch.net/lagerlogistik-optimierung.html).
