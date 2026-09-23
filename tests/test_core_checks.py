"""Die 7 Korrektheits-Checks der Vorab-Messreihe (lager-planung/messreihe_wellen_konflikt/check.py) als pytest-Tests.
Alles ganzzahlig und deterministisch, keine Toleranzen noetig. Der CP-Test bleibt fuer CI klein (wenige Kleininstanzen,
kurzes Zeitlimit) und behauptet nur, was beweisbar ist - keine Wall-Clock-Assertions."""
import heapq

import pytest

from wfg_cp import solve_cp
from wfg_scenario import Cfg, make_instance
from wfg_sim import simulate


def hand_instance(due1: int) -> dict:
    b = lambda m: dict(visits=[(0, 100)], walks=[0, 0], aisles={0}, D=100, members=[m], due=due1)  # noqa: E731
    return dict(cfg=Cfg(n_aisles=2), orders={}, batches=[b(0), b(1)],
                order_info={0: (0, 1000, 1), 1: (1, due1, 1)}, K=2)


# 1 ---------------------------------------------------------------------------------------------------
def test_hand_instance_blocking_costs_exactly_one_aisle_duration():
    """Zwei identische Batches in EINEM Gang, zwei Kommissionierer: der zweite wartet exakt die Dauer des ersten."""
    inst = hand_instance(150)
    on = simulate(inst, policy="fifo", blocking=True)
    off = simulate(inst, policy="fifo", blocking=False)
    assert on["comp"] == [100, 200] and on["wait"] == 100 and on["obj"] == 50, on
    assert off["comp"] == [100, 100] and off["wait"] == 0 and off["obj"] == 0, off
    # verspaetete Bestellungen: mit Blockieren nur die mit Frist 150 (fertig 200), ohne Blockieren keine
    assert on["late"] == 1 and off["late"] == 0
    assert simulate(hand_instance(50), policy="fifo", blocking=False)["late"] == 1      # fertig 100 > 50, die andere (Frist 1000) puenktlich


# 2 ---------------------------------------------------------------------------------------------------
def test_single_picker_never_blocks():
    for seed in range(30):
        inst = make_instance(Cfg(), seed, k=1)
        a = simulate(inst, K=1, policy="edd", blocking=True)
        b = simulate(inst, K=1, policy="edd", blocking=False)
        assert a["comp"] == b["comp"] and a["wait"] == 0, seed


# 3 ---------------------------------------------------------------------------------------------------
def list_scheduling(inst: dict, K: int, policy: str) -> list[int]:
    """Unabhaengig geschriebenes List-Scheduling auf K identischen Maschinen (Dauer = Gesamtarbeit D des Batches)."""
    B = inst["batches"]
    order = list(range(len(B))) if policy == "fifo" else sorted(range(len(B)), key=lambda b: (B[b]["due"], b))
    free = [0] * K
    heapq.heapify(free)
    comp = [0] * len(B)
    for b in order:
        t = heapq.heappop(free)
        comp[b] = t + B[b]["D"]
        heapq.heappush(free, comp[b])
    return comp


@pytest.mark.parametrize("pol", ["fifo", "edd"])
@pytest.mark.parametrize("K", [2, 4, 6])
def test_blocking_off_equals_independent_list_scheduling(pol, K):
    """Ohne Blockieren ist es klassisches List-Scheduling (das Modell der warehouse-transfer-demo)."""
    for seed in range(40):
        inst = make_instance(Cfg(), seed, k=K)
        assert simulate(inst, K=K, policy=pol, blocking=False)["comp"] == list_scheduling(inst, K, pol), (seed, K, pol)


# 4 ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pol,w", [("fifo", 1), ("edd", 1), ("edd_w", 3)])
def test_runtime_identity_and_aisle_exclusivity(pol, w):
    """Jede Batch-Laufzeit = Arbeit + Wartezeit (Summe ueber alle), und kein Gang ist je doppelt belegt."""
    for seed in range(40):
        inst = make_instance(Cfg(n_pickers=5), seed)
        r = simulate(inst, policy=pol, w=w, blocking=True, log=True)
        B = inst["batches"]
        assert sum(r["comp"][b] - r["start"][b] for b in range(len(B))) == r["work"] + r["wait"], (seed, pol)
        for log in r["aisle_log"]:
            log.sort()
            for (e1, x1, *_), (e2, x2, *_) in zip(log, log[1:]):
                assert e2 >= x1, (seed, pol, "Gang doppelt belegt")


# 5 ---------------------------------------------------------------------------------------------------
def test_instance_sanity():
    for seed in range(40):
        cfg = Cfg()
        inst = make_instance(cfg, seed)
        covered = sorted(o for b in inst["batches"] for o in b["members"])
        assert covered == list(range(cfg.n_orders)), seed
        for b in inst["batches"]:
            assert sum(len(inst["orders"][o]["items"]) for o in b["members"]) <= cfg.capacity
            assert b["due"] == min(inst["order_info"][o][1] for o in b["members"])
        assert make_instance(cfg, seed)["batches"] == inst["batches"]


# 6 ---------------------------------------------------------------------------------------------------
def test_window_rule_is_exercised():
    """Regressionstest: edd_w mit w=1 ist exakt EDD, mit w>1 weicht es auf mindestens einer Instanz ab (frueher wurde
    der Fenster-Zweig nie erreicht: ein fruehes return verdeckte ihn, alle Differenzen waren exakt 0,00 +- 0,00)."""
    differs = 0
    for seed in range(60):
        inst = make_instance(Cfg(n_pickers=5), seed)
        base = simulate(inst, policy="edd")
        assert simulate(inst, policy="edd_w", w=1)["comp"] == base["comp"], seed
        if simulate(inst, policy="edd_w", w=4)["comp"] != base["comp"]:
            differs += 1
    assert differs > 0, "edd_w mit w=4 weicht nie von EDD ab - Fenster-Regel wird nicht ausgefuehrt"


# 7 ---------------------------------------------------------------------------------------------------
def test_cp_reference_is_never_beaten_by_a_heuristic():
    """CP-SAT-Optimum darf von keiner Heuristik unterboten werden (deren Plaene sind im CP-Modell zulaessig); das
    Optimum ohne Blockieren ist eine Relaxation. Nur Beweisbares: ein bewiesenes Optimum <= Heuristik, jede Schranke
    <= Heuristik, Relaxations-Schranke <= jede zulaessige Loesung mit Blockieren."""
    cfg = Cfg(n_aisles=6, n_orders=18, n_pickers=3)
    proven = 0
    for seed in range(4):
        inst = make_instance(cfg, seed)
        opt = solve_cp(inst, blocking=True, time_limit=5, workers=2)
        relax = solve_cp(inst, blocking=False, time_limit=5, workers=2)
        heur = min(simulate(inst, policy=p, w=w)["obj"] for p, w in (("fifo", 1), ("edd", 1), ("edd_w", 2), ("edd_w", 4)))
        assert opt["status"] in ("OPTIMAL", "FEASIBLE"), (seed, opt)
        if opt["status"] == "OPTIMAL":
            proven += 1
            assert opt["obj"] <= heur, (seed, opt, heur)
        assert opt["bound"] <= heur + 1e-6, (seed, opt, heur)
        assert relax["bound"] <= opt["obj"] + 1e-6, (seed, relax, opt)
        if opt["status"] == "OPTIMAL" and relax["status"] == "OPTIMAL":
            assert relax["obj"] <= opt["obj"], (seed, relax, opt)
    assert proven >= 1, "auf 18 Bestellungen muss mindestens ein Lauf bewiesen optimal sein"


# 7b: CP-Modell an Handinstanzen (exakt bekannt, schnell) ---------------------------------------------------------
def _two_identical_batches(due=50):
    b = lambda m: dict(visits=[(0, 100)], walks=[0, 0], aisles={0}, D=100, members=[m], due=due)  # noqa: E731
    return dict(cfg=Cfg(n_aisles=2), orders={}, batches=[b(0), b(1)], order_info={0: (0, due, 1), 1: (1, due, 1)}, K=2)


def test_cp_hand_instance_blocking_and_relaxation_optima_are_exact():
    """Zwei identische Batches (Dauer 100) in EINEM Gang, Frist 50, K=2: ohne Blockieren fertig 100/100 (Verspaetung
    50+50), mit Blockieren 100/200 (50+150)."""
    inst = _two_identical_batches()
    with_blocking = solve_cp(inst, blocking=True, time_limit=10, workers=1)
    without = solve_cp(inst, blocking=False, time_limit=10, workers=1)
    assert with_blocking["status"] == "OPTIMAL" and with_blocking["obj"] == 200
    assert without["status"] == "OPTIMAL" and without["obj"] == 100
    assert simulate(inst, policy="edd")["obj"] == 200 and simulate(inst, policy="edd", blocking=False)["obj"] == 100


def test_cp_hand_instance_cumulative_limit_serializes_with_one_picker():
    """K=1: selbst ohne Gang-Ausschluss darf nur ein Batch zur Zeit laufen (Cumulative)."""
    inst = _two_identical_batches()
    assert solve_cp(inst, K=1, blocking=False, time_limit=10, workers=1)["obj"] == 200
    assert solve_cp(inst, K=2, blocking=False, time_limit=10, workers=1)["obj"] == 100


def test_cp_exact_size_guard_needs_both_limits():
    import wfg_constants as C
    from wfg_cp import exact_size_ok
    small = make_instance(Cfg(n_orders=24), 0)
    assert exact_size_ok(small) and len(small["batches"]) <= C.EXACT_MAX_BATCHES
    many_orders = make_instance(Cfg(n_orders=C.EXACT_MAX_ORDERS + 1), 0)          # Bestellungslimit verletzt, Batchlimit nicht
    assert len(many_orders["batches"]) <= C.EXACT_MAX_BATCHES and not exact_size_ok(many_orders)
    many_batches = make_instance(Cfg(n_orders=25, capacity=6), 0)                 # Batchlimit verletzt, Bestellungslimit nicht
    assert len(many_batches["batches"]) > C.EXACT_MAX_BATCHES and not exact_size_ok(many_batches)
    edge = make_instance(Cfg(n_orders=C.EXACT_MAX_ORDERS), 0)
    assert exact_size_ok(edge) == (len(edge["batches"]) <= C.EXACT_MAX_BATCHES)   # genau 30 Bestellungen sind erlaubt


def test_cp_objective_weights_the_orders():
    """Gewichte zaehlen im CP-Ziel (Express = 3): zwei identische Batches in einem Gang, Frist 50, der erste mit Gewicht 3.
    Der gewichtete Batch laeuft zuerst (fertig 100: 3 x 50), der andere danach (fertig 200: 150) - Optimum 300, nicht 200."""
    inst = _two_identical_batches()
    inst["order_info"] = {0: (0, 50, 3), 1: (1, 50, 1)}
    res = solve_cp(inst, blocking=True, time_limit=10, workers=1)
    assert res["status"] == "OPTIMAL" and res["obj"] == 300
    assert solve_cp(inst, blocking=False, time_limit=10, workers=1)["obj"] == 3 * 50 + 50


def test_cp_exact_size_guard_boundaries_are_inclusive():
    from wfg_cp import exact_size_ok
    import wfg_constants as C
    fake = lambda nb, no: dict(batches=[None] * nb, orders=[None] * no)  # noqa: E731
    assert exact_size_ok(fake(C.EXACT_MAX_BATCHES, C.EXACT_MAX_ORDERS))              # genau 10 Batches, 30 Bestellungen: erlaubt
    assert not exact_size_ok(fake(C.EXACT_MAX_BATCHES + 1, C.EXACT_MAX_ORDERS))
    assert not exact_size_ok(fake(C.EXACT_MAX_BATCHES, C.EXACT_MAX_ORDERS + 1))
    assert exact_size_ok(fake(1, 1))
