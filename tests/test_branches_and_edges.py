"""Zweig-Test je Regel (jede Regel muss auf mindestens einer Instanz ein anderes Ergebnis liefern als ihre Nachbarregel -
sonst ist ein Zweig womoeglich nie erreicht) und die Randfaelle aus Plan Abschnitt 11."""
from dataclasses import replace

import pytest

import wfg_constants as C
import wfg_evaluation as E
from wfg_scenario import Cfg, make_instance
from wfg_sim import _choose, simulate


def _differs(cfg, run_a, run_b, n=80):
    return sum(1 for s in range(n) if simulate(make_instance(cfg, s), **run_a)["comp"]
               != simulate(make_instance(cfg, s), **run_b)["comp"])


# ---------------------------------------------------------------------------------------------------
# Zweig je Regel
# ---------------------------------------------------------------------------------------------------
def test_fifo_and_edd_differ_on_many_instances():
    assert _differs(Cfg(), dict(policy="fifo"), dict(policy="edd")) > 40


def test_edd_and_window_two_differ_on_at_least_one_instance():
    assert _differs(Cfg(), dict(policy="edd"), dict(policy="edd_w", w=2)) > 0


def test_window_neighbours_differ_on_at_least_one_instance():
    assert _differs(Cfg(), dict(policy="edd_w", w=2), dict(policy="edd_w", w=4)) > 0
    assert _differs(Cfg(), dict(policy="edd_w", w=4), dict(policy="edd_w", w=8)) > 0


def test_window_one_is_exactly_edd_on_every_instance():
    assert _differs(Cfg(), dict(policy="edd"), dict(policy="edd_w", w=1)) == 0


def test_rule_kwargs_use_distinct_policy_names():
    names = {E.rule_kwargs(rule, 3)["policy"] for rule in C.RULE_KEYS}
    assert names == {"fifo", "edd", "edd_w"}


def test_window_rule_chooses_the_candidate_with_fewer_aisle_conflicts():
    """Handinstanz: B0 (Frist 0) belegt Gang 0; EDD gibt danach B1 (Frist 1, will ebenfalls Gang 0) frei, das Fenster
    (w=2) dagegen B2 (Frist 2, Gang 5, kein Konflikt)."""
    def batch(aisle, due, member):
        return dict(visits=[(aisle, 1000)], walks=[0, 0], aisles={aisle}, D=1000, members=[member], due=due)
    inst = dict(cfg=Cfg(n_aisles=6), orders={}, batches=[batch(0, 0, 0), batch(0, 1, 1), batch(5, 2, 2)],
                order_info={0: (0, 0, 1), 1: (1, 1, 1), 2: (2, 2, 1)}, K=2)
    assert simulate(inst, policy="edd")["start"] == [0, 0, 1000]          # EDD: B1 sofort, B2 muss warten
    assert simulate(inst, policy="edd_w", w=2)["start"] == [0, 1000, 0]   # Fenster: B2 sofort
    # das Fenster ist ein echtes Fenster: mit w=1 sieht es B2 nicht
    assert simulate(inst, policy="edd_w", w=1)["start"] == [0, 0, 1000]


def test_window_larger_than_number_of_waiting_batches():
    B = [dict(aisles={a}, due=a, visits=[(a, 10)]) for a in range(3)]
    assert _choose({2}, {}, B, "edd_w", 8) == 2                  # nur ein wartender Batch
    assert _choose({1, 2}, {}, B, "edd_w", 8) == 1               # kein aktiver Batch -> alle Konflikte 0 -> Frist
    inst = make_instance(Cfg(n_orders=20, n_pickers=2), 3)
    assert simulate(inst, policy="edd_w", w=8)["obj"] >= 0       # w groesser als die Batchzahl wartender: kein Absturz


def test_unknown_policy_is_rejected():
    inst = make_instance(Cfg(n_orders=20), 1)
    with pytest.raises(AssertionError):
        simulate(inst, policy="lifo")


def test_fifo_takes_the_lowest_index_regardless_of_due_dates():
    B = [dict(aisles={0}, due=100, visits=[(0, 1)]), dict(aisles={0}, due=1, visits=[(0, 1)])]
    assert _choose({0, 1}, {}, B, "fifo", 1) == 0
    assert _choose({0, 1}, {}, B, "edd", 1) == 1


def test_a_column_of_exact_zeros_is_a_bug_signal_not_a_finding():
    """Die Fenster-Gewinne duerfen nicht ueber alle Regime exakt 0,00 +- 0,00 sein (so blieb der Zweig unbemerkt)."""
    gains = [E.evaluate_population(Cfg(), w).gain() for w in (2, 4, 8)]
    assert all(g.mean != 0.0 and g.se != 0.0 for g in gains)


# ---------------------------------------------------------------------------------------------------
# Randfaelle (Plan Abschnitt 11)
# ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("cfg", [
    Cfg(n_pickers=2), Cfg(n_aisles=4), Cfg(n_orders=20), Cfg(express_share=0.05), Cfg(hot_corr=0.0), Cfg(hot_corr=1.0),
    Cfg(tau=0.4), Cfg(tau=2.0), Cfg(n_aisles=12, n_orders=100, n_pickers=10), Cfg(n_aisles=4, n_pickers=10, n_orders=20),
], ids=["K=2", "4 Gaenge", "20 Bestellungen", "Express 5%", "rho 0", "rho 100", "tau 0,4", "tau 2,0", "Maximum", "eng+viele"])
@pytest.mark.parametrize("rule", C.RULE_KEYS)
def test_edge_settings_simulate_consistently(cfg, rule):
    for seed in range(6):
        inst = make_instance(cfg, seed)
        r = simulate(inst, log=True, **E.rule_kwargs(rule, 8))
        B = inst["batches"]
        assert all(c is not None for c in r["comp"])
        assert sum(r["comp"][b] - r["start"][b] for b in range(len(B))) == r["work"] + r["wait"]
        assert r["obj"] >= 0 and 0 <= r["late"] <= cfg.n_orders


def test_single_batch_instance():
    cfg = Cfg(n_orders=3, items_max=4, n_pickers=4)                   # hoechstens 12 Positionen <= Kapazitaet 15
    for seed in range(10):
        inst = make_instance(cfg, seed)
        assert len(inst["batches"]) == 1
        for rule in C.RULE_KEYS:
            r = simulate(inst, **E.rule_kwargs(rule, 4))
            assert r["wait"] == 0 and r["comp"] == [inst["batches"][0]["D"]]


def test_population_edge_bounds_are_finite_and_paired():
    for cfg in (Cfg(n_pickers=2, n_aisles=4, n_orders=20), Cfg(n_pickers=10, n_aisles=12, n_orders=100)):
        pop = E.evaluate_population(cfg, 8)
        assert pop.n == C.N_POPULATION
        for pair in (pop.gain(), pop.advantage_on(), pop.advantage_off(), pop.advantage_change()):
            assert pair.se >= 0 and pair.mean == pair.mean


def test_tight_deadlines_hurt_more_than_loose_ones():
    tight = E.evaluate_population(replace(Cfg(), tau=0.4), 1).mean_min("edd")
    loose = E.evaluate_population(replace(Cfg(), tau=2.0), 1).mean_min("edd")
    assert tight > loose


def test_minimum_express_share_still_makes_rho_matter():
    """Express-Anteil 5 %: rho darf nicht wirkungslos sein (deshalb das Minimum von 5 % im Regler)."""
    cfg = Cfg(express_share=0.05, hot_corr=0.0)
    a = E.evaluate_population(cfg, 1).obj["edd"]
    b = E.evaluate_population(replace(cfg, hot_corr=1.0), 1).obj["edd"]
    assert a != b


def test_minimum_pickers_still_blocks_and_fewer_aisles_block_more():
    cfg = Cfg(n_pickers=2)
    assert E.evaluate_population(cfg, 1).wait_share_pct("edd") > 0.0
    assert (E.evaluate_population(replace(cfg, n_aisles=4), 1).wait_share_pct("edd")
            > E.evaluate_population(replace(cfg, n_aisles=12), 1).wait_share_pct("edd"))


@pytest.mark.parametrize("rule", C.RULE_KEYS)
def test_late_count_is_the_number_of_orders_with_positive_tardiness(rule):
    """Die Zahl verspaeteter Bestellungen wird unabhaengig aus Fertigstellung und Frist nachgezaehlt."""
    for seed in range(15):
        inst = make_instance(Cfg(n_pickers=4), seed)
        r = simulate(inst, **E.rule_kwargs(rule, 3))
        recount = sum(1 for bi, due, _ in inst["order_info"].values() if r["comp"][bi] > due)
        assert r["late"] == recount, (seed, rule)
        assert 0 < r["late"] < len(inst["orders"])                 # bei tau 0,8 weder alle noch keine puenktlich
