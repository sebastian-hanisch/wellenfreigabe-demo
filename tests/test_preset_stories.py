"""Erfuellen die echten Presets ihre eigenen Abnahmekriterien - auf der 80-Instanzen-Population, reproduziert aus
demselben Code? Alles deterministisch (siehe tools/tune_presets.py fuer die Abstimmung)."""
import pytest

import wfg_constants as C
import wfg_evaluation as E
import wfg_stories as ST


def _pop(name):
    p = C.PRESETS[name]
    cfg = E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])
    return E.evaluate_population(cfg, p["window"])


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_preset_satisfies_its_own_acceptance_criteria(name):
    for ok, text in ST.criteria(name, ST.metrics_from_population(_pop(name))):
        assert ok, f"{name}: {text}"


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_shown_seed_is_qualitatively_consistent_with_the_population(name):
    """Die gezeigte Einzelinstanz (Gantt) ist ein einzelner Seed ausserhalb der Stichprobe und bleibt qualitativ:
    Blockieren tritt dort auf, wo die Population es zeigt, und fehlt nicht, wo sie es zeigt (kein Widerspruch)."""
    p = C.PRESETS[name]
    cfg = E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])
    pop = _pop(name)
    inst, res = E.shown_run(cfg, p["seed"], C.RULE_EDDW, p["window"])
    s = E.shown_summary(inst, res)
    pop_wait = pop.wait_share_pct(C.RULE_EDDW)
    assert s["wait_share_pct"] > 0.0
    assert 0.5 * pop_wait <= s["wait_share_pct"] <= 1.5 * pop_wait


def test_each_story_shows_up_in_the_sign_pattern_of_the_window_gain():
    """Kernaussage der Demo (Plan Abschnitt 1): das Vorzeichen des Fenster-Effekts haengt vom Regime ab."""
    verdicts = {name: _pop(name).gain().verdict() for name in C.PRESETS}
    assert verdicts["Standard"] == "pos"
    assert verdicts["Wenige Kommissionierer"] == "neg"
    assert verdicts["Enge Fristen, heiße Gänge"] == "pos"
    assert verdicts["Lockere Fristen"] == "neg"
    assert verdicts["Viele Kommissionierer"] == "none"      # ehrlich: hier kein belastbarer Unterschied


def test_wait_share_grows_with_pickers_across_the_three_pickers_presets():
    w = {name: _pop(name).wait_share_pct("edd") for name in ("Wenige Kommissionierer", "Standard", "Viele Kommissionierer")}
    assert w["Wenige Kommissionierer"] < w["Standard"] < w["Viele Kommissionierer"]
