"""Auswertung: gepaarte Statistik, Urteil in drei Zustaenden an der 2-SE-Schwelle, Meldungszustaende, Population gegen
Direktrechnung, Reproduktion der Messreihe (Zahlen aus sweep_data.json exakt, da deterministisch), Sweeps, Exakt-Zusammenfassung."""
import json
import pathlib
import statistics as st
from dataclasses import replace

import pytest

import wfg_constants as C
import wfg_evaluation as E
from wfg_scenario import Cfg, make_instance
from wfg_sim import simulate

REF = json.loads((pathlib.Path(__file__).parent / "data" / "sweep_reference.json").read_text(encoding="utf-8"))
PRESET_KEYS = {"Standard": "standard", "Wenige Kommissionierer": "wenige", "Viele Kommissionierer": "viele",
               "Enge Fristen, heiße Gänge": "eng_heiss", "Lockere Fristen": "locker"}


def _cfg(p):
    return E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])


# ---------------------------------------------------------------------------------------------------
# Paarstatistik und Urteil
# ---------------------------------------------------------------------------------------------------
def test_paired_matches_direct_computation():
    a, b = [10, 20, 30, 45], [5, 25, 30, 20]
    d = [5, -5, 0, 25]
    p = E.paired(a, b)
    assert p.mean == pytest.approx(st.mean(d) / 600) and p.se == pytest.approx(st.stdev(d) / 2 / 600)


def test_paired_sign_convention_is_first_minus_second():
    assert E.paired([600, 1200], [0, 0]).mean > 0
    assert E.paired([0, 0], [600, 1200]).mean < 0


def test_paired_of_a_single_pair_has_zero_se_and_empty_is_zero():
    assert E.paired([600], [0]) == E.Pair(1.0, 0.0)
    assert E.pair_from_diffs([]) == E.Pair(0.0, 0.0)


def test_verdict_flips_exactly_at_two_standard_errors():
    assert E.Pair(2.0, 1.0).verdict() == "none"           # genau 2 SE ist noch nicht belastbar
    assert E.Pair(2.001, 1.0).verdict() == "pos"
    assert E.Pair(-2.0, 1.0).verdict() == "none"
    assert E.Pair(-2.001, 1.0).verdict() == "neg"
    assert E.Pair(0.0, 0.0).verdict() == "none"           # exakt null ist kein Befund
    assert E.Pair(0.001, 0.0).verdict() == "pos"


def test_message_state_four_states_and_thresholds():
    pos, neg, none = E.Pair(10, 2), E.Pair(-10, 2), E.Pair(1, 2)
    assert E.message_state(16.0, pos) == E.STATE_PAYS
    assert E.message_state(16.0, neg) == E.STATE_HURTS
    assert E.message_state(16.0, none) == E.STATE_UNCLEAR
    assert E.message_state(4.9, pos) == E.STATE_IRRELEVANT and E.message_state(4.9, neg) == E.STATE_IRRELEVANT
    assert E.message_state(4.999, pos) == E.STATE_IRRELEVANT       # Schwelle 5 %: darunter irrelevant
    assert E.message_state(5.0, pos) == E.STATE_PAYS               # ab 5 % zaehlt das Vorzeichen


# ---------------------------------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------------------------------
def test_cfg_from_controls_maps_percent_points_to_shares():
    cfg = E.cfg_from_controls(6, 3, 40, 0.5, 30, 70)
    assert (cfg.n_aisles, cfg.n_pickers, cfg.n_orders, cfg.tau) == (6, 3, 40, 0.5)
    assert cfg.express_share == 0.30 and cfg.hot_corr == 0.70


def test_population_against_direct_simulation():
    cfg = Cfg(n_orders=30, n_pickers=3)
    pop = E.evaluate_population(cfg, 3)
    assert pop.n == 80 and pop.w == 3
    for seed in (0, 17, 79):
        inst = make_instance(cfg, seed)
        assert pop.obj["fifo"][seed] == simulate(inst, policy="fifo")["obj"]
        assert pop.obj["edd"][seed] == simulate(inst, policy="edd")["obj"]
        assert pop.obj["edd_w"][seed] == simulate(inst, policy="edd_w", w=3)["obj"]
        assert pop.obj["edd_free"][seed] == simulate(inst, policy="edd", blocking=False)["obj"]
        assert pop.late["edd"][seed] == simulate(inst, policy="edd")["late"]
    assert pop.wait_share["edd_free"] == 0.0
    assert pop.mean_min("edd") == st.fmean(pop.obj["edd"]) / 600
    assert pop.late_share_pct("edd") == pytest.approx(st.fmean(pop.late["edd"]) / 30 * 100)


def test_gain_and_diff_signs_are_reference_minus_rule_and_rule_minus_edd():
    pop = E.evaluate_population(Cfg(), 2)
    assert pop.gain().mean == pytest.approx(pop.mean_min("edd") - pop.mean_min("edd_w"))
    assert pop.diff_to_edd("edd_w").mean == pytest.approx(-pop.gain().mean)
    assert pop.diff_to_edd("fifo").mean == pytest.approx(pop.mean_min("fifo") - pop.mean_min("edd"))
    assert pop.advantage_on().mean == pytest.approx(pop.mean_min("fifo") - pop.mean_min("edd"))
    assert pop.advantage_off().mean == pytest.approx(pop.mean_min("fifo_free") - pop.mean_min("edd_free"))
    assert pop.advantage_change().mean == pytest.approx(pop.advantage_on().mean - pop.advantage_off().mean)


def test_window_one_gain_is_exactly_zero_by_definition():
    g = E.evaluate_population(Cfg(), 1).gain()
    assert g == E.Pair(0.0, 0.0)


def test_population_instances_are_cached_and_deterministic():
    cfg = Cfg(n_orders=25)
    assert E.population_instances(cfg) is E.population_instances(cfg)
    assert E.evaluate_population(cfg, 2).obj == E.evaluate_population(cfg, 2).obj


# ---------------------------------------------------------------------------------------------------
# Reproduktion der Messreihe (sweep_data.json)
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(C.PRESETS))
def test_presets_reproduce_the_measurement_series_exactly(name):
    p = C.PRESETS[name]
    ref = REF["presets"][PRESET_KEYS[name]]
    cfg = _cfg(p)
    assert {k: getattr(cfg, k) for k in ref["cfg"]} == ref["cfg"]
    pop = E.evaluate_population(cfg, p["window"])
    for ours, theirs in (("fifo", "fifo"), ("edd", "edd"), ("edd_free", "edd_ohne_blockieren"),
                         ("fifo_free", "fifo_ohne_blockieren")):
        assert pop.mean_min(ours) == pytest.approx(ref["obj_min"][theirs], rel=1e-12), (name, ours)
    assert pop.mean_min("edd_w") == pytest.approx(ref["obj_min"][f"w{p['window']}"], rel=1e-12)
    assert pop.wait_share_pct("edd") == pytest.approx(ref["wait_share_pct"], rel=1e-12)
    assert pop.n_batches == pytest.approx(ref["n_batches"])
    for pair, key in ((pop.advantage_on(), "edd_vs_fifo_advantage_on"), (pop.advantage_off(), "edd_vs_fifo_advantage_off"),
                      (pop.gain(), f"gain_w{p['window']}")):
        assert pair.mean == pytest.approx(ref[key]["mean"], rel=1e-12) and pair.se == pytest.approx(ref[key]["se"], rel=1e-12)


@pytest.mark.parametrize("w", [2, 4, 8])
def test_all_three_windows_reproduce_the_standard_preset(w):
    ref = REF["presets"]["standard"]
    pop = E.evaluate_population(_cfg(C.PRESETS["Standard"]), w)
    assert pop.gain().mean == pytest.approx(ref[f"gain_w{w}"]["mean"], rel=1e-12)
    assert pop.gain().se == pytest.approx(ref[f"gain_w{w}"]["se"], rel=1e-12)


def test_k_sweep_reproduces_the_measurement_series():
    rows = {r.k: r for r in E.k_sweep(Cfg())}
    assert list(rows) == list(range(2, 11))
    for k_str, ref in REF["k_sweep"].items():
        row = rows[int(k_str)]
        assert row.adv_on.mean == pytest.approx(ref["edd_vs_fifo_advantage_on"]["mean"], rel=1e-12)
        assert row.adv_off.mean == pytest.approx(ref["edd_vs_fifo_advantage_off"]["mean"], rel=1e-12)
        assert row.rel_change_pct == pytest.approx(
            (ref["edd_vs_fifo_advantage_on"]["mean"] / ref["edd_vs_fifo_advantage_off"]["mean"] - 1) * 100, rel=1e-9)


def test_k_sweep_differs_from_k_to_k_and_has_a_belastbar_decline_at_many_pickers():
    rows = E.k_sweep(Cfg())
    assert len({round(r.adv_on.mean, 6) for r in rows}) == len(rows)          # keine Spalte identischer Werte
    assert all(r.change.mean != 0 for r in rows)
    assert rows[0].verdict == "none"                                          # K=2: kaum Blockieren
    assert all(r.verdict == "neg" for r in rows if r.k >= 6)                  # viele Kommissionierer: belastbar weniger


def test_relative_change_pct_and_zero_denominator():
    assert E.relative_change_pct(50.0, 100.0) == -50.0
    assert E.relative_change_pct(150.0, 100.0) == 50.0
    assert E.relative_change_pct(5.0, 0.0) == 0.0


def test_rho_sweep_shape_sign_pattern_and_counts():
    cfg = Cfg(n_pickers=4)
    rows = E.rho_sweep(cfg)
    assert list(rows) == [0, 50, 100] and all(list(v) == [2, 4, 8] for v in rows.values())
    assert rows[100][2].verdict() == "pos"                                    # heiss + eng (tau 0,8): hilft
    assert rows[0][8].verdict() == "neg"                                      # unabhaengig, grosses Fenster: schadet
    counts = E.verdict_counts(rows)
    assert sum(counts.values()) == 9 and counts["pos"] >= 1 and counts["neg"] >= 1
    # jede Zelle einzeln gegen die Population bei diesem rho
    for rho, by_w in rows.items():
        for w, pair in by_w.items():
            assert pair == E.evaluate_population(replace(cfg, hot_corr=rho / 100), w).gain()


def test_verdict_counts_on_artificial_cells():
    cells = {0: {2: E.Pair(5, 1), 4: E.Pair(-5, 1)}, 50: {2: E.Pair(1, 1), 4: E.Pair(0, 0)}}
    assert E.verdict_counts(cells) == {"pos": 1, "neg": 1, "none": 2}


# ---------------------------------------------------------------------------------------------------
# Gezeigte Instanz, Exakt-Zusammenfassung
# ---------------------------------------------------------------------------------------------------
def test_shown_example_reproduces_the_reference_instance():
    ex = REF["example"]
    cfg = Cfg(n_aisles=ex["n_aisles"], n_orders=24, n_pickers=ex["K"])
    inst, res = E.shown_run(cfg, ex["seed"], C.RULE_EDD, 1)
    assert res["wait"] == ex["wait_ds"] and res["makespan"] == ex["makespan_ds"] and res["comp"] == ex["comp"]
    assert [[list(e) for e in log] for log in res["aisle_log"]] == ex["aisle_log"]
    s = E.shown_summary(inst, res)
    assert s["obj_min"] == pytest.approx(ex["obj_min"]) and s["n_batches"] == 7


def test_shown_summary_fields():
    inst, res = E.shown_run(Cfg(n_pickers=4), 5, C.RULE_EDDW, 2)
    s = E.shown_summary(inst, res)
    assert s["wait_share_pct"] == pytest.approx(res["wait"] / (res["work"] + res["wait"]) * 100)
    assert s["makespan_min"] == res["makespan"] / 600 and s["late"] == res["late"]


def test_exact_summary_percentages_and_flags():
    inst = make_instance(Cfg(n_aisles=6, n_orders=24, n_pickers=3), 51)
    edd = simulate(inst, policy="edd")["obj"]
    opt = dict(status="OPTIMAL", obj=int(edd * 0.8), bound=float(int(edd * 0.8)), wall=1.5)
    free = dict(status="FEASIBLE", obj=int(edd * 0.6), bound=float(int(edd * 0.5)), wall=2.0)
    x = E.exact_summary(inst, 2, opt, free)
    assert x["proven"] and not x["proven_free"]
    assert x["potential_pct"] == pytest.approx((edd - opt["obj"]) / edd * 100)
    assert x["price_pct"] == pytest.approx((opt["obj"] - free["obj"]) / free["obj"] * 100)
    assert x["opt_min"] == opt["obj"] / 600 and x["bound_free_min"] == free["bound"] / 600
    assert x["edd_min"] == edd / 600 and x["wall_s"] == 3.5


def test_exact_summary_zero_denominators_give_none():
    """Nichts verspaetet (EDD-Wert 0) und Optimum ohne Blockieren 0: keine Prozentwerte (Division durch 0)."""
    b = lambda m: dict(visits=[(0, 100)], walks=[0, 0], aisles={0}, D=100, members=[m], due=1000)  # noqa: E731
    inst = dict(cfg=Cfg(n_aisles=2), orders={}, batches=[b(0), b(1)], order_info={0: (0, 1000, 1), 1: (1, 1000, 1)}, K=2)
    assert simulate(inst, policy="edd")["obj"] == 0
    zero = dict(status="OPTIMAL", obj=0, bound=0.0, wall=0.1)
    x = E.exact_summary(inst, 2, zero, zero)
    assert x["price_pct"] is None and x["potential_pct"] is None and x["potential_eddw_pct"] is None
