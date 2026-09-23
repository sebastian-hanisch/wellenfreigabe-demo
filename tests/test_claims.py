"""JEDE Zahl aus dem README und den App-Texten wird hier nachgerechnet (Playbook: erst messen, dann Text schreiben).
Alles deterministisch (Seeds 0..79). Die exakten CP-SAT-Zahlen der Vorab-Messung (Optimum 19,6 % / 13,0 % unter EDD,
Blockier-Aufpreis 29,2 % / 35,1 %) stehen im README ausdruecklich als Vorab-Messung und sind NICHT Teil der CI-Tests:
sie brauchen Loeser-Laeufe mit Zeitlimit (siehe messreihe_wellen_konflikt/cp_gap.json)."""
import pathlib

import wfg_constants as C
import wfg_evaluation as E
from wfg_scenario import Cfg


def _one(x, digits=1):
    return f"{x:.{digits}f}"


def _pop(name):
    p = C.PRESETS[name]
    cfg = E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])
    return E.evaluate_population(cfg, p["window"])


def test_standard_lager_numbers_in_the_readme():
    pop = _pop("Standard")
    assert _one(pop.wait_share_pct("edd")) == "16.3"
    assert _one(pop.mean_min("edd_free")) == "139.5" and _one(pop.mean_min("edd")) == "279.3"
    assert _one(pop.mean_min("edd") / pop.mean_min("edd_free")) == "2.0"
    g = pop.gain()
    assert (_one(g.mean), _one(g.se)) == ("11.9", "3.6") and g.verdict() == "pos"
    assert _one(pop.n_batches) == "17.1"                                        # "etwa 17 Batches"
    assert _one(pop.mean_min("fifo")) == "371.1"


def test_blocking_share_grows_from_four_to_forty_two_percent():
    ks = {r.k: E.evaluate_population(Cfg(n_pickers=r.k), 1).wait_share_pct("edd") for r in E.k_sweep(Cfg())}
    assert _one(ks[2]) == "4.0" and _one(ks[8]) == "42.1"
    assert all(ks[k] < ks[k + 1] for k in range(2, 10))                         # monoton in der Kommissionierer-Zahl


def test_advantage_erosion_by_pickers():
    rows = {r.k: r for r in E.k_sweep(Cfg())}
    expected = {3: ("156.1", "147.3", "-5.6"), 4: ("114.9", "91.8", "-20.1"), 6: ("66.2", "28.2", "-57.4")}
    for k, (off, on, rel) in expected.items():
        assert (_one(rows[k].adv_off.mean), _one(rows[k].adv_on.mean), _one(rows[k].rel_change_pct)) == (off, on, rel), k
    assert _one(rows[2].adv_off.mean) == "240.8" and _one(rows[2].adv_on.mean) == "240.5"
    assert rows[8].rel_change_pct < -70 and rows[10].rel_change_pct < -75


def test_erosion_is_belastbar_from_three_pickers_on():
    rows = {r.k: r for r in E.k_sweep(Cfg())}
    assert rows[2].verdict == "none" and all(rows[k].verdict == "neg" for k in range(3, 11))


def test_few_pickers_control_case():
    pop = _pop("Wenige Kommissionierer")
    assert _one(pop.wait_share_pct("edd")) == "4.0"
    assert (_one(pop.advantage_on().mean), _one(pop.advantage_off().mean)) == ("240.5", "240.8")
    g = pop.gain()
    assert (_one(g.mean), _one(g.se)) == ("-11.0", "3.5") and g.verdict() == "neg"        # w = 4


def test_many_pickers_case():
    pop = _pop("Viele Kommissionierer")
    assert _one(pop.wait_share_pct("edd")) == "30.7"
    assert _one(pop.advantage_on().mean / pop.advantage_off().mean * 100) == "42.6"
    assert pop.gain().verdict() == "none"                                        # w = 2: kein belastbarer Unterschied


def test_the_two_regimes_of_the_window():
    eng, locker = _pop("Enge Fristen, heiße Gänge").gain(), _pop("Lockere Fristen").gain()
    assert (_one(eng.mean), _one(eng.se)) == ("17.9", "5.3") and eng.verdict() == "pos"
    assert (_one(locker.mean), _one(locker.se)) == ("-41.1", "3.0") and locker.verdict() == "neg"


def test_rho_sweep_sign_pattern_in_the_standard_lager():
    rows = E.rho_sweep(_cfg_standard())
    assert (_one(rows[100][2].mean), _one(rows[100][2].se)) == ("10.0", "3.3") and rows[100][2].verdict() == "pos"
    assert (_one(rows[0][8].mean), _one(rows[0][8].se)) == ("-32.4", "5.9") and rows[0][8].verdict() == "neg"
    assert _one(rows[0][4].mean) == "-8.4" and rows[0][4].verdict() == "neg"
    assert E.verdict_counts(rows) == {"pos": 1, "neg": 2, "none": 6}


def _cfg_standard():
    p = C.PRESETS["Standard"]
    return E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])


def test_readme_numbers_match_the_tests():
    """Jede im README genannte Zahl steht auch in diesem Test (Stichprobe der Schluesselzahlen)."""
    readme = (pathlib.Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")
    for needle in ("139,5", "279,3", "16,3 %", "+11,9 ± 3,6", "156,1", "147,3", "-5,6 %", "114,9", "91,8", "-20,1 %", "66,2",
                   "28,2", "-57,4 %", "4,0 %", "42,1 %", "30,7 %", "42,6 %", "+17,9 ± 5,3", "-41,1 ± 3,0", "-11,0 ± 3,5",
                   "240,5", "240,8", "19,6 %", "13,0 %", "29,2 %", "35,1 %"):
        assert needle in readme, needle


def test_app_text_numbers():
    """Zahlen der App-Texte: Vorab-Messung im Exakt-Tab und die Rechenzeit-Angabe im Kernabschnitt."""
    app = (pathlib.Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    for needle in ("19,6 %", "13,0 %", "29,2 %", "35,1 %", "12-s-Limit", "etwa 6 ms", "etwa 60 ms"):
        assert needle in app, needle
    assert C.EXACT_MAX_BATCHES == 10 and C.EXACT_MAX_ORDERS == 30 and C.EXACT_TIME_LIMIT == 20.0
