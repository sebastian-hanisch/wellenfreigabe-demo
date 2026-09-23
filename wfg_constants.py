"""Konstanten der Wellenfreigabe-Demo (Kommissionierwellen: Fristen und Gangblockaden, Lager-Linie).

Modell und Zahlen aus messreihe_wellen_konflikt/ (siehe lager-planung/plan_wellen_konflikt.html und
messreihe_wellen_konflikt/ERGEBNIS.md). Fachmodell-Konstanten (Ganglaenge, Gangabstand, Gehgeschwindigkeit,
Pickzeit, Kapazitaet je Batch, heisse Gaenge, Express-Gewicht) sind FEST - Plan Abschnitt 5 exponiert dafuer
keine Regler. Einstellbar sind Gaenge, Kommissionierer, Bestellungen, Fristendruck, Express-Anteil,
Konzentration auf vordere Gaenge (rho), Konflikt-Fenster w und der Seed.

Prozent-Regler (Express-Anteil, rho) liegen in GANZZAHLIGEN Prozentpunkten - `format="%d%%"` in app.py
formatiert damit direkt den Reglerwert (bekannte Falle: format="%.0f%%" formatiert den ROHEN Wert)."""

# --- Regler (Plan Abschnitt 5): (Minimum, Maximum), Standard ---------------------------------------
AISLES_RANGE, AISLES_DEFAULT = (4, 12), 8
PICKERS_RANGE, PICKERS_DEFAULT = (2, 10), 4        # Minimum 2: sonst gibt es kein Blockieren (toter Regler)
ORDERS_RANGE, ORDERS_DEFAULT = (20, 100), 60
TAU_RANGE, TAU_DEFAULT, TAU_STEP = (0.4, 2.0), 0.8, 0.1   # kleiner = engere Fristen
EXPRESS_PCT_RANGE, EXPRESS_PCT_DEFAULT = (5, 50), 25       # Minimum 5 %: sonst ist rho wirkungslos
HOT_CORR_PCT_RANGE, HOT_CORR_PCT_DEFAULT, HOT_CORR_STEP = (0, 100), 80, 5
WINDOW_RANGE, WINDOW_DEFAULT = (1, 8), 2                  # w = 1 ist exakt EDD
SEED_RANGE, SEED_DEFAULT = (0, 9999), 264

# --- Stichprobe hinter den Kennzahlen (Plan Abschnitt 5/6): Seeds 0..79 des Reglerstands ---------------
N_POPULATION = 80
MIN_DS = 600                       # Dezisekunden je Minute (alle Zeiten der Simulation sind ganzzahlig in ds)
K_SWEEP_RANGE = tuple(range(2, 11))          # Kernabschnitt: Kommissionierer 2..10
RHO_SWEEP_PCT = (0, 50, 100)                # Kernabschnitt: Konzentration auf vordere Gaenge
WINDOW_SWEEP = (2, 4, 8)                    # Kernabschnitt: Fenstergroessen

# --- Meldungen der Hauptansicht (Plan Abschnitt 6) -------------------------------------------------
WAIT_SHARE_LOW_PCT = 5.0           # darunter: "Blockieren spielt hier kaum eine Rolle"
SE_FACTOR = 2.0                    # "belastbar" = mehr als 2 Standardfehler

# --- Exakt-Tab (Plan Abschnitt 8): CP-SAT nur fuer Kleininstanzen -------------------------------------
EXACT_MAX_BATCHES = 10
EXACT_MAX_ORDERS = 30
EXACT_TIME_LIMIT = 20.0            # Sekunden je Loesung (mit und ohne Blockieren)
EXACT_COOLDOWN_SECONDS = 20        # Abkuehlpause nach einem Lauf
EXACT_WORKERS = 4

# --- Regeln (Plan Abschnitt 3) -------------------------------------------------------------------------
RULE_FIFO, RULE_EDD, RULE_EDDW = "fifo", "edd", "edd_w"
RULE_KEYS = (RULE_FIFO, RULE_EDD, RULE_EDDW)
RULE_LABELS = {
    RULE_FIFO: "🐌 FIFO",
    RULE_EDD: "📅 EDD",
    RULE_EDDW: "🚧 EDD mit Konflikt-Fenster",
}
RULE_SHORT = {RULE_FIFO: "FIFO", RULE_EDD: "EDD", RULE_EDDW: "EDD mit Fenster"}
EXACT_TAB_LABEL = "🎯 Exakt (nur Kleininstanzen)"
COMPARISON_TAB_LABEL = "📊 Vergleich"
RULE_DESCRIPTIONS = {
    RULE_FIFO: "Gibt die Batches in der Reihenfolge ihrer Bildung frei, ohne Fristen zu beachten. Die "
               "**Kontrast-Baseline**: zeigt, was eine fristenbewusste Regel überhaupt wert ist.",
    RULE_EDD: "Gibt immer den Batch mit der **frühesten Frist** als Nächstes frei (Earliest Due Date). Blind dafür, "
              "wo andere Kommissionierer gerade sind. Die **fristenbewusste Basisregel** und der Vergleichsmaßstab "
              "des Konflikt-Fensters.",
    RULE_EDDW: "Betrachtet die **w dringendsten** Batches und gibt daraus den frei, der die **wenigsten Gangkonflikte** "
               "mit gerade aktiven Batches hat (Gleichstand nach Frist). Bei w = 1 ist das exakt EDD. Die "
               "**Untersuchungsregel**: die Demo zeigt, wann sie hilft und wann sie schadet - keine pauschale Empfehlung.",
}

# --- Farben (konsistent ueber alle Figuren) ------------------------------------------------------------
RULE_COLORS = {RULE_FIFO: "#9aa5b4", RULE_EDD: "#2a6fb0", RULE_EDDW: "#c77700"}
NO_BLOCKING_COLOR = "#9aa5b4"
BLOCKING_COLOR = "#2a6fb0"
WINDOW_COLORS = {2: "#e0a800", 4: "#d2691e", 8: "#c0392b"}
BATCH_COLORS = ("#2a6fb0", "#2e7d4f", "#e0a800", "#7d5ba6", "#d2691e", "#17a2b8", "#c0392b")
WAIT_COLOR = "#5b6b80"
CHART_HEIGHT = 380

# --- Presets (Plan Abschnitt 7; mit tools/tune_presets.py gegen wfg_stories.criteria() abgestimmt) --------
# Der Seed bestimmt nur die GEZEIGTE Instanz (Gantt), die Kennzahlen stehen auf den Seeds 0..79. Die Anzeige-Seeds
# liegen ausserhalb der Stichprobe und kommen aus `tools/tune_presets.py --seeds` (repraesentativ: Wartezeitanteil und
# Verspaetung nahe am Populationsmittel des Presets).
PRESETS = {
    "Standard": dict(aisles=8, pickers=4, orders=60, tau=0.8, express_pct=25, hot_corr_pct=80, window=2, seed=264),
    "Wenige Kommissionierer": dict(aisles=8, pickers=2, orders=60, tau=0.8, express_pct=25, hot_corr_pct=80,
                                   window=4, seed=193),
    "Viele Kommissionierer": dict(aisles=8, pickers=6, orders=60, tau=0.8, express_pct=25, hot_corr_pct=80,
                                  window=2, seed=140),
    "Enge Fristen, heiße Gänge": dict(aisles=8, pickers=4, orders=60, tau=0.5, express_pct=25, hot_corr_pct=100,
                                      window=4, seed=294),
    "Lockere Fristen": dict(aisles=8, pickers=4, orders=60, tau=1.6, express_pct=25, hot_corr_pct=0,
                            window=4, seed=273),
}
PRESET_HELP = {
    "Standard": "Der Grundfall: Blockieren kostet spürbar, ein kleines Fenster holt einen Teil zurück.",
    "Wenige Kommissionierer": "Kontrollfall: kaum Blockieren, die Fristenregel genügt - und das Fenster schadet.",
    "Viele Kommissionierer": "Der Blockier-Fall: die Fristenregel verliert mehr als die Hälfte ihres Vorteils.",
    "Enge Fristen, heiße Gänge": "Hier lohnt Konfliktvermeidung - der schmale Bereich, in dem das Fenster hilft.",
    "Lockere Fristen": "Das Gegenstück: dieselbe Regel kostet mehr, als sie bringt.",
}
