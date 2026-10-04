"""AppTest: Skelett und Footer, jedes Preset, Permalink, alle Regler an Min und Max, alle vier Meldungszustaende, Exakt-Tab
(Groessenpruefung, Button-Pfad mit Stub und mit kurzem echtem Limit, Cooldown, Veralten), PDF, Texte."""
import pathlib
import time

import pytest
from streamlit.testing.v1 import AppTest

import wfg_constants as C
import wfg_cp as CP
import wfg_evaluation as E
from wfg_presets import PRESET_STATE_KEYS, SETTING_SPECS

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
FOOTER = (
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Lagerlogistik optimieren](https://sebastianhanisch.net/lagerlogistik-optimierung.html)."
)


@pytest.fixture(autouse=True)
def clean_state():
    """st.cache_data ist prozessweit, ebenso die Kernkette der Zwischenspeicher: Tests duerfen keine Ergebnisse anderer
    Tests sehen."""
    import streamlit as st
    st.cache_data.clear()
    yield


def fresh(**query):
    at = AppTest.from_file(APP, default_timeout=180)
    for k, v in query.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, at.exception
    return at


def set_and_run(at, **values):
    for key, value in values.items():
        (at.number_input(key=key) if key == "seed_input" else at.slider(key=key)).set_value(value)
    at.run()
    assert not at.exception, at.exception
    return at


def main_metrics(at):
    return [(m.label, m.value) for m in at.metric[:4]]


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception
    return at


def message(at, needle):
    for group in (at.success, at.warning, at.info, at.error):
        for x in group:
            if needle in x.value:
                return x.value
    return None


# ---------------------------------------------------------------------------------------------------
# Skelett
# ---------------------------------------------------------------------------------------------------
def test_skeleton_and_footer():
    at = fresh()
    assert [h.value for h in at.sidebar.header] == ["⚙️ Einstellungen"]                   # genau EIN Header
    assert len(at.title) == 1 and "Kommissionierwellen" in at.title[0].value
    assert any(v.value.startswith("## 🚧") for v in at.markdown)
    assert any(v.value.startswith("### 📐 Wie viel Vorteil bleibt der Fristenregel") for v in at.markdown)
    assert [e.label for e in at.expander] == ["🔧 Wie wir das erreichen – Regeln im Vergleich",
                                              "Wie funktioniert diese Demo?", "📐 Mathematische Formulierung"]
    assert any(c.value == FOOTER for c in at.caption)
    presets = [b.label for b in at.button if b.label in C.PRESETS]
    assert presets == list(C.PRESETS) and len(presets) == 5 and all(len(n) <= 32 for n in presets)
    assert [s.label for s in at.sidebar.slider] == ["Gänge", "Kommissionierer", "Bestellungen", "Fristendruck",
                                                    "Express-Anteil", "Konzentration auf vordere Gänge",
                                                    "Konflikt-Fenster w"]
    assert [n.label for n in at.sidebar.number_input] == ["Seed"]
    assert [b.label for b in at.sidebar.button] == ["🎲 Neue Instanz"]                     # letztes Sidebar-Element
    order = [type(e).__name__ for e in at.sidebar.children.values()]
    assert order[-1] == "Button"


def test_sidebar_has_no_second_header_or_subheader():
    at = fresh()
    assert len(at.sidebar.header) == 1 and len(at.sidebar.subheader) == 0


def test_main_metrics_are_2x2_with_the_right_labels():
    at = fresh()
    assert [m[0] for m in main_metrics(at)] == ["Verspätung (EDD mit Fenster w = 2)", "Verspätung ohne Blockieren (Regel EDD)",
                                                "Wartezeitanteil (Regel EDD)", "Gewinn des Fensters ggü. EDD"]
    values = dict(main_metrics(at))
    assert values["Wartezeitanteil (Regel EDD)"] == "16,3 %" and values["Verspätung ohne Blockieren (Regel EDD)"] == "139,5 Min."
    assert "+11,9 ± 3,6" in values["Gewinn des Fensters ggü. EDD"]


def test_charts_are_present_with_unique_keys():
    at = fresh()
    keys = [c.key for c in at.get("plotly_chart")]
    assert len(set(keys)) == len(keys) and all(keys)
    # Gantt (Haupt) + 2 Kernabschnitt + 3 Regel-Tabs (je Gantt) + Vergleichs-Tab (2 Kernabschnitt-Grafiken) = 8
    assert len(keys) == 8
    assert {"main_gantt", "core_k_chart", "core_rho_chart", "tab_fifo_gantt", "tab_edd_gantt", "tab_eddw_gantt",
            "comparison_tab_k_chart", "comparison_tab_rho_chart"} == set(keys)


def test_comparison_table_has_one_row_per_rule_plus_reference():
    at = fresh()
    df = [d for d in at.dataframe if "Regel" in d.value.columns][-1].value
    assert list(df["Regel"])[:3] == [C.RULE_LABELS[r] + (" (w = 2)" if r == C.RULE_EDDW else "") for r in C.RULE_KEYS]
    assert "ohne Blockieren" in df["Regel"].iloc[-1]
    assert list(df.columns) == ["Regel", "Gewichtete Verspätung (Min.)", "Differenz zu EDD (Min., ± SE)", "Wartezeitanteil",
                                "Verspätete Bestellungen"]


def test_each_rule_tab_shows_its_own_gantt():
    at = fresh()
    keys = [c.key for c in at.get("plotly_chart")]
    assert sum(1 for k in keys if k.endswith("_gantt")) == 4                # Haupt + 3 Tabs


def test_pdf_download_button_is_offered():
    at = fresh()
    buttons = at.get("download_button")
    assert len(buttons) == 1 and buttons[0].proto.label == "📄 Ergebnis als PDF herunterladen"


def test_texts_state_the_model_the_honest_limits_and_the_nonwinner():
    at = fresh()
    text = "\n".join(m.value for m in at.expander[1].markdown)
    for needle in ("S-Shape", "Einzelressource", "FIFO", "EDD", "Konflikt-Fenster", "heißen Gänge", "bedingte Aussage",
                   "Nicht kalibriert", "Kleininstanzen", "Standardfehler"):
        assert needle in text, needle
    math_text = "\n".join(m.value for m in at.expander[2].markdown)
    for needle in ("NoOverlap", "Cumulative", "warehouse-transfer-demo", "quaycrane-demo", "wfg_sim.py"):
        assert needle in math_text, needle
    intro = at.markdown[0].value
    assert "order_batch-demo" in intro and "Wie funktioniert diese Demo?" in intro and "📐 Mathematische Formulierung" in intro


# ---------------------------------------------------------------------------------------------------
# Presets, Permalink
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_loads_within_widget_bounds_and_shows_its_story(name):
    at = fresh()
    click(at, name)
    preset = C.PRESETS[name]
    for field, key in PRESET_STATE_KEYS.items():
        widget = at.number_input(key=key) if key == "seed_input" else at.slider(key=key)
        assert widget.value == preset[field], (name, field)
    assert main_metrics(at)[0][0] == f"Verspätung (EDD mit Fenster w = {preset['window']})"


def test_permalink_is_clamped_snapped_and_ignores_garbage():
    at = fresh(a="999", k="abc", tau="0.87", rho="83", ex="0", w="0", junk="ignored")
    assert at.slider(key="aisles_slider").value == C.AISLES_RANGE[1]                # geklemmt
    assert at.slider(key="pickers_slider").value == C.PICKERS_DEFAULT               # Muell ignoriert
    assert at.slider(key="tau_slider").value == 0.9                                 # auf Zehntel eingerastet
    assert at.slider(key="hot_corr_slider").value == 85                             # auf 5er-Schritt eingerastet
    assert at.slider(key="express_slider").value == C.EXPRESS_PCT_RANGE[0]          # Minimum 5 %
    assert at.slider(key="window_slider").value == C.WINDOW_RANGE[0]


def test_permalink_roundtrip_reflects_settings():
    at = fresh(a="6", k="3", n="45", tau="0.5", ex="30", rho="100", w="4", seed="11")
    values = {k: at.session_state[k] for k in SETTING_SPECS}
    assert values == {"aisles_slider": 6, "pickers_slider": 3, "orders_slider": 45, "tau_slider": 0.5,
                      "express_slider": 30, "hot_corr_slider": 100, "window_slider": 4, "seed_input": 11}
    for key, spec in SETTING_SPECS.items():
        got = at.query_params[spec.url_param]
        got = got[0] if isinstance(got, list) else got
        assert got == spec.encoder(at.session_state[key]), key


def test_new_instance_button_changes_only_the_seed_and_randomizes():
    at = fresh()
    before = {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"}
    seeds = set()
    for _ in range(6):
        click(at, "🎲 Neue Instanz")
        seeds.add(at.session_state["seed_input"])
        assert C.SEED_RANGE[0] <= at.session_state["seed_input"] <= C.SEED_RANGE[1]
    assert len(seeds) > 1
    assert {k: at.session_state[k] for k in SETTING_SPECS if k != "seed_input"} == before


def test_seed_changes_only_the_gantt_not_the_population_metrics():
    at = fresh()
    before = main_metrics(at)
    at = set_and_run(at, seed_input=555)
    assert main_metrics(at) == before


# ---------------------------------------------------------------------------------------------------
# Regler an den Grenzen
# ---------------------------------------------------------------------------------------------------
SLIDERS = [("aisles_slider", C.AISLES_RANGE), ("pickers_slider", C.PICKERS_RANGE), ("orders_slider", C.ORDERS_RANGE),
           ("tau_slider", C.TAU_RANGE), ("express_slider", C.EXPRESS_PCT_RANGE),
           ("hot_corr_slider", C.HOT_CORR_PCT_RANGE), ("window_slider", C.WINDOW_RANGE)]


@pytest.mark.parametrize("key,idx", [(k, i) for k, _ in SLIDERS for i in (0, 1)])
def test_every_slider_works_at_its_minimum_and_maximum(key, idx):
    value = dict(SLIDERS)[key][idx]
    at = set_and_run(fresh(), **{key: value})
    assert at.session_state[key] == value and len(at.metric) >= 4


def test_seed_input_works_at_its_minimum_and_maximum():
    for value in C.SEED_RANGE:
        at = set_and_run(fresh(), seed_input=value)
        assert at.session_state["seed_input"] == value


def test_extreme_combinations_run_without_exception():
    fresh(a="4", k="10", n="100", tau="0.4", ex="50", rho="100", w="8", seed="0")
    fresh(a="12", k="2", n="20", tau="2.0", ex="5", rho="0", w="1", seed="9999")
    fresh(a="4", k="2", n="20", tau="0.4", ex="5", rho="0", w="8", seed="1")


def test_no_slider_is_a_dead_control():
    """Jeder Regler veraendert an mindestens einer Grenze eine Kennzahl der Hauptansicht (kein Regler ist unter einer
    anderen Einstellung ein dokumentiertes No-Op); Minima von Express-Anteil und Kommissionierern bleiben wirksam."""
    base = main_metrics(fresh())
    for key, (lo, hi) in SLIDERS:
        for value in (lo, hi):
            if value == SETTING_SPECS[key].default:
                continue
            assert main_metrics(set_and_run(fresh(), **{key: value})) != base, (key, value)
    # Minimum Express-Anteil (5 %) und Minimum Kommissionierer (2): rho bzw. K wirken weiterhin
    assert main_metrics(fresh(ex="5", n="20", rho="0")) != main_metrics(fresh(ex="5", n="20", rho="100"))
    assert main_metrics(fresh(k="2", rho="100", tau="0.5")) != main_metrics(fresh(k="2", rho="0", tau="0.5"))


# ---------------------------------------------------------------------------------------------------
# Bedingte Meldung: alle vier Zustaende
# ---------------------------------------------------------------------------------------------------
def test_message_pays_off_for_the_standard_preset():
    at = fresh()
    assert message(at, "Hier lohnt Konfliktvermeidung") is not None
    assert at.success


def test_message_irrelevant_for_few_pickers_and_mentions_the_window_harm():
    at = click(fresh(), "Wenige Kommissionierer")
    msg = message(at, "Blockieren spielt hier kaum eine Rolle")
    assert msg is not None and "schlechter" in msg                                   # die Geschichte des Presets steht drin


def test_message_hurts_for_loose_deadlines():
    at = click(fresh(), "Lockere Fristen")
    assert message(at, "kostet Konfliktvermeidung mehr, als sie bringt") is not None
    assert at.warning


def test_message_unclear_for_many_pickers():
    at = click(fresh(), "Viele Kommissionierer")
    assert message(at, "Kein belastbarer Unterschied") is not None


def test_message_at_window_one_explains_that_the_window_is_off():
    at = set_and_run(fresh(), window_slider=1)
    assert message(at, "w = 1 ist exakt EDD") is not None
    assert dict(main_metrics(at))["Gewinn des Fensters ggü. EDD"].startswith("+0,0")


def test_each_preset_shows_exactly_one_state_message_of_the_four():
    needles = ["Hier lohnt Konfliktvermeidung", "Blockieren spielt hier kaum eine Rolle",
               "kostet Konfliktvermeidung mehr, als sie bringt", "Kein belastbarer Unterschied"]
    seen = set()
    for name in C.PRESETS:
        at = click(fresh(), name)
        hits = [n for n in needles if message(at, n) is not None]
        assert len(hits) == 1, (name, hits)
        seen.add(hits[0])
    assert seen == set(needles)                                                       # alle vier Zustaende erreichbar


# ---------------------------------------------------------------------------------------------------
# Kernabschnitt
# ---------------------------------------------------------------------------------------------------
def test_core_section_sentence_for_the_current_picker_count():
    at = fresh()
    assert message(at, "Bei Ihren 4 Kommissionierern schrumpft der Vorteil der Fristenregel") is not None
    at = set_and_run(fresh(), pickers_slider=2)
    assert message(at, "Bei Ihren 2 Kommissionierern verändert das Blockieren den Vorteil der Fristenregel nicht belastbar") is not None


def test_core_section_tables_are_present():
    at = fresh()
    tables = [d.value for d in at.dataframe]
    ks = [t for t in tables if "Kommissionierer" in t.columns and "Vorteil mit Blockieren (Min.)" in t.columns]
    rhos = [t for t in tables if "Konzentration ρ" in t.columns]
    assert len(ks) == 1 and list(ks[0]["Kommissionierer"]) == list(range(2, 11))
    assert len(rhos) == 1 and list(rhos[0]["Konzentration ρ"]) == ["0 %", "50 %", "100 %"]


# ---------------------------------------------------------------------------------------------------
# Exakt-Tab
# ---------------------------------------------------------------------------------------------------
def _fake_solve(calls):
    def solve(inst, K=None, blocking=True, time_limit=20.0, workers=8):
        calls.append(dict(blocking=blocking, time_limit=time_limit, workers=workers))
        from wfg_sim import simulate
        edd = simulate(inst, policy="edd")["obj"]
        return dict(status="OPTIMAL", obj=int(edd * (0.75 if blocking else 0.55)), bound=float(int(edd * (0.75 if blocking else 0.55))),
                    wall=0.1)
    return solve


SMALL = dict(n="24")


def test_exact_tab_shows_the_size_hint_for_large_instances():
    at = fresh()
    assert message(at, "für den exakten Solver zu groß") is not None
    assert not [b for b in at.button if b.key == "exact_solve_button"]                # kein Knopf bei zu grosser Instanz


def test_exact_tab_size_guard_is_driven_by_the_orders_and_batches_limits():
    assert not CP.exact_size_ok(E.shown_run(E.cfg_from_controls(8, 4, 60, 0.8, 25, 80), 264, C.RULE_EDD, 1)[0])
    assert CP.exact_size_ok(E.shown_run(E.cfg_from_controls(8, 4, 24, 0.8, 25, 80), 264, C.RULE_EDD, 1)[0])
    at = fresh(**SMALL)
    assert message(at, "für den exakten Solver zu groß") is None
    assert [b for b in at.button if b.key == "exact_solve_button"]
    assert message(at, "Noch nicht gelöst") is not None


def test_exact_tab_button_path_with_stub_solver(monkeypatch):
    calls = []
    monkeypatch.setattr(CP, "solve_cp", _fake_solve(calls))
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    assert not at.exception, at.exception
    assert [c["blocking"] for c in calls] == [True, False]                            # mit und ohne Blockieren
    assert all(c["time_limit"] == C.EXACT_TIME_LIMIT == 20.0 for c in calls)
    labels = [m.label for m in at.metric]
    assert "Optimum (mit Blockieren)" in labels and "Optimum ohne Blockieren" in labels
    assert "Potenzial ggü. EDD" in labels and "Preis des Blockierens im Optimum" in labels
    val = {m.label: m.value for m in at.metric}
    assert val["Potenzial ggü. EDD"].endswith("%") and val["Preis des Blockierens im Optimum"].startswith("+")
    # der Vergleich-Tab bekommt die Exakt-Zeile ebenfalls (Vollrerun nach dem Loesen)
    assert any("Exakt (nur gezeigte Kleininstanz)" in m.value for m in at.markdown)


def test_exact_tab_cooldown_disables_the_button_and_expires(monkeypatch):
    monkeypatch.setattr(CP, "solve_cp", _fake_solve([]))
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    assert at.button(key="exact_solve_button").disabled                               # Abkuehlpause aktiv
    assert any("Abkühlpause aktiv" in c.value for c in at.caption)
    at.session_state["exact_last_run_at"] = time.time() - C.EXACT_COOLDOWN_SECONDS - 1   # Pause vorbei
    at.run()
    assert not at.exception, at.exception
    assert not at.button(key="exact_solve_button").disabled


def test_exact_tab_result_goes_stale_when_the_instance_changes(monkeypatch):
    monkeypatch.setattr(CP, "solve_cp", _fake_solve([]))
    monkeypatch.setattr(C, "EXACT_COOLDOWN_SECONDS", 0)
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    assert any(m.label == "Optimum (mit Blockieren)" for m in at.metric)
    at = set_and_run(at, seed_input=777)
    assert message(at, "bitte erneut lösen") is not None
    assert not any(m.label == "Optimum (mit Blockieren)" for m in at.metric)
    # ein anderer Fenster-Wert veraltet das Ergebnis NICHT (Loesung haengt nicht von w ab)
    at = set_and_run(at, seed_input=int(at.session_state["seed_input"]))
    at.button(key="exact_solve_button").click().run()
    at = set_and_run(at, window_slider=5)
    assert any(m.label == "Optimum (mit Blockieren)" for m in at.metric)


def _unproven_solver(free_proven):
    def solve(inst, K=None, blocking=True, time_limit=20.0, workers=8):
        from wfg_sim import simulate
        edd = simulate(inst, policy="edd")["obj"]
        if blocking or not free_proven:
            return dict(status="FEASIBLE", obj=int(edd * 0.8), bound=float(int(edd * 0.4)), wall=20.0)
        return dict(status="OPTIMAL", obj=int(edd * 0.5), bound=float(int(edd * 0.5)), wall=1.0)
    return solve


def test_exact_tab_reports_unproven_results_honestly(monkeypatch):
    monkeypatch.setattr(CP, "solve_cp", _unproven_solver(free_proven=False))
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    assert not at.exception, at.exception
    labels = [m.label for m in at.metric]
    assert "Beste Lösung (mit Blockieren)" in labels and "Beste Lösung ohne Blockieren" in labels
    assert "Potenzial ggü. EDD (mindestens)" in labels and "Preis des Blockierens (Näherung)" in labels
    assert "Optimum (mit Blockieren)" not in labels and "Preis des Blockierens im Optimum" not in labels
    assert any("Nicht bewiesene Werte sind Näherungen" in c.value for c in at.caption)


def test_exact_tab_price_is_only_an_upper_bound_when_just_the_relaxation_is_proven(monkeypatch):
    monkeypatch.setattr(CP, "solve_cp", _unproven_solver(free_proven=True))
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    labels = [m.label for m in at.metric]
    assert "Preis des Blockierens (höchstens)" in labels and "Optimum ohne Blockieren" in labels


def test_exact_tab_handles_a_missing_solver_without_crashing(monkeypatch):
    def broken(*a, **k):
        raise ImportError("no ortools")
    monkeypatch.setattr(CP, "solve_cp", broken)
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    assert not at.exception, at.exception
    assert any("nicht installiert" in e.value for e in at.error)
    assert not any(m.label == "Optimum (mit Blockieren)" for m in at.metric)


def test_exact_tab_button_path_with_a_real_short_solve(monkeypatch):
    """Echter CP-SAT-Lauf mit kurzem Limit auf einer kleinen Instanz. Nur Beweisbares wird behauptet: Ergebnisse
    erscheinen, Werte sind endlich, und die Relaxation ist nur dann nicht schlechter, wenn BEIDE Laeufe bewiesen sind."""
    monkeypatch.setattr(C, "EXACT_TIME_LIMIT", 3.0)
    monkeypatch.setattr(C, "EXACT_WORKERS", 2)
    at = fresh(n="18", k="3", a="6")
    at.button(key="exact_solve_button").click().run()
    assert not at.exception, at.exception
    val = {m.label: m.value for m in at.metric}
    blk = [k for k in ("Optimum (mit Blockieren)", "Beste Lösung (mit Blockieren)") if k in val]
    free = [k for k in ("Optimum ohne Blockieren", "Beste Lösung ohne Blockieren") if k in val]
    assert len(blk) == 1 and len(free) == 1 and val[blk[0]].endswith("Min.") and val[free[0]].endswith("Min.")
    if blk[0].startswith("Optimum") and free[0].startswith("Optimum"):
        assert float(val[free[0]][:-5].replace(",", ".")) <= float(val[blk[0]][:-5].replace(",", ".")) + 0.05


def test_pdf_still_works_with_an_exact_result(monkeypatch):
    monkeypatch.setattr(CP, "solve_cp", _fake_solve([]))
    at = fresh(**SMALL)
    at.button(key="exact_solve_button").click().run()
    assert not at.exception, at.exception
    assert len(at.get("download_button")) == 1
