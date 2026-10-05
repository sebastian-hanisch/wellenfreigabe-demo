"""Orakel für CP-SAT-Referenz, Simulation und Instanzerzeugung.

* CP-SAT-Optimum gegen Vollaufzählung (alle Kommissionierer-Zuordnungen und Reihenfolgen x alle Gang-Reihenfolgen, Längster-Weg-Rechnung im Netzplan), mit und ohne Blockieren.
  Der Zielwert muss gerundet werden (CP-SAT meldet 1626.9999999999998 für 1627; ein abgeschnittener int-Wert lag um eine Dezisekunde zu niedrig).
* Simulation gegen eine zweite Fassung ohne Ereignisliste (kleinster nächster Zeitpunkt über die Kommissionierer; Gleichstand nach Erzeugungsreihenfolge des Ereignisses).
* S-Shape-Route, Batching und die Gangverteilung der Express-Positionen (ρ = 0: Anteil der vorderen Gänge aus den Gewichten exp(-0,15 a)) von Hand."""

import itertools
import math
import random

import pytest

from wfg_cp import solve_cp
from wfg_scenario import Cfg, build_route, make_instance
from wfg_sim import simulate

pytest.importorskip("ortools")


def _brute_force(inst, K, blocking):
    B = inst["batches"]
    nb = len(B)
    nodes = [(b, i) for b in range(nb) for i in range(len(B[b]["visits"]))]
    dur = {(b, i): B[b]["visits"][i][1] for b, i in nodes}
    aisle = {(b, i): B[b]["visits"][i][0] for b, i in nodes}
    structures = {}
    for perm in itertools.permutations(range(nb)):
        for cuts in itertools.combinations_with_replacement(range(nb + 1), K - 1):
            parts, prev = [], 0
            for c in list(cuts) + [nb]:
                parts.append(perm[prev:c])
                prev = c
            structures[tuple(sorted(parts))] = parts
    by_aisle = {}
    for n in nodes:
        by_aisle.setdefault(aisle[n], []).append(n)
    aisle_orders = list(itertools.product(*[itertools.permutations(v) for v in by_aisle.values()])) if blocking else [()]
    best = math.inf
    for ao in aisle_orders:
        for parts in structures.values():
            edges = [((b, i), (b, i + 1), dur[(b, i)] + B[b]["walks"][i + 1]) for b in range(nb) for i in range(len(B[b]["visits"]) - 1)]
            for seq in parts:
                for x, y in zip(seq, seq[1:]):
                    last = len(B[x]["visits"]) - 1
                    edges.append(((x, last), (y, 0), dur[(x, last)] + B[x]["walks"][-1] + B[y]["walks"][0]))
            for order in ao:
                edges += [(u, v, dur[u]) for u, v in zip(order, order[1:])]
            indeg, adj = {n: 0 for n in nodes}, {n: [] for n in nodes}
            for u, v, length in edges:
                adj[u].append((v, length))
                indeg[v] += 1
            start = {n: (B[n[0]]["walks"][0] if n[1] == 0 else 0) for n in nodes}
            stack, seen = [n for n in nodes if indeg[n] == 0], 0
            while stack:
                u = stack.pop()
                seen += 1
                for v, length in adj[u]:
                    start[v] = max(start[v], start[u] + length)
                    indeg[v] -= 1
                    if indeg[v] == 0:
                        stack.append(v)
            if seen < len(nodes):
                continue                                                                       # Gang-Reihenfolge und Kommissionierer-Folge widersprechen sich
            end = [start[(b, len(B[b]["visits"]) - 1)] + dur[(b, len(B[b]["visits"]) - 1)] + B[b]["walks"][-1] for b in range(nb)]
            best = min(best, sum(w * max(0, end[bi] - d) for bi, d, w in inst["order_info"].values()))
    return best


def _hand_instance():
    """Zwei Kommissionierer, ohne Blockieren: Batch 0 fertig bei 378, Batch 1 bei 298; Optimum 3*(378-104) + (378-239) + 3*(298-76) = 1627."""
    batches = [
        dict(visits=[(0, 206), (1, 126)], walks=[0, 23, 23], aisles={0, 1}, D=378, due=104, members=[0, 1]),
        dict(visits=[(0, 126), (1, 126)], walks=[0, 23, 23], aisles={0, 1}, D=298, due=76, members=[2]),
    ]
    return dict(cfg=Cfg(n_aisles=2), orders={}, batches=batches, order_info={0: (0, 104, 3), 1: (0, 239, 1), 2: (1, 76, 3)}, K=2)


def test_exact_objective_is_rounded_not_truncated():
    result = solve_cp(_hand_instance(), K=2, blocking=False, time_limit=10, workers=2)
    assert result["status"] == "OPTIMAL" and result["obj"] == 1627
    assert _brute_force(_hand_instance(), 2, False) == 1627


@pytest.mark.parametrize("blocking", [True, False])
def test_cp_optimum_equals_exhaustive_enumeration(blocking):
    rng = random.Random(7 if blocking else 8)
    checked = 0
    while checked < 25:
        cfg = Cfg(n_aisles=rng.randint(2, 3), n_pickers=rng.randint(1, 3), n_orders=rng.randint(3, 6), capacity=rng.choice([3, 4, 5]), items_min=1, items_max=rng.choice([2, 3]),
                  tau=rng.choice([0.2, 0.4, 0.8, 1.2]), express_share=rng.choice([0.0, 0.5]), hot_corr=0.5, aisle_len=rng.choice([30.0, 6.0]))
        inst = make_instance(cfg, rng.randrange(10000))
        n_batches, n_visits = len(inst["batches"]), sum(len(b["visits"]) for b in inst["batches"])
        if not 2 <= n_batches <= 4 or n_visits > 8:
            continue
        optimum = _brute_force(inst, cfg.n_pickers, blocking)
        result = solve_cp(inst, K=cfg.n_pickers, blocking=blocking, time_limit=20, workers=2)
        assert result["status"] == "OPTIMAL" and result["obj"] == optimum
        for policy in ("fifo", "edd"):
            assert simulate(inst, K=cfg.n_pickers, policy=policy, blocking=blocking)["obj"] >= optimum
        checked += 1


def _other_simulation(inst, K, policy, w, blocking):
    B, n_aisles = inst["batches"], inst["cfg"].n_aisles
    waiting = list(range(len(B)))
    pickers = [dict(t=0, kind="free", b=None, i=0, stamp=p) for p in range(K)]
    stamp, aisle_free, comp, start, wait, active = K, [0] * n_aisles, [None] * len(B), [None] * len(B), 0, {}
    while any(p["t"] is not None for p in pickers):
        p = min((p for p in pickers if p["t"] is not None), key=lambda q: (q["t"], q["stamp"]))
        t = p["t"]
        if p["kind"] == "free":
            if not waiting:
                p["t"] = None
                continue
            by_due = sorted(waiting, key=lambda b: (B[b]["due"], b))
            if policy == "fifo":
                b = min(waiting)
            elif policy == "edd":
                b = by_due[0]
            else:
                rest = [{a for a, _ in B[ab]["visits"][i:]} for ab, i in active.items()]
                b = min(by_due[:w], key=lambda x: (sum(len(B[x]["aisles"] & r) for r in rest), B[x]["due"], x))
            waiting.remove(b)
            active[b], start[b] = 0, t
            p.update(kind="arrive", b=b, i=0, t=t + B[b]["walks"][0], stamp=stamp)
        else:
            b, i = p["b"], p["i"]
            a, d = B[b]["visits"][i]
            entry = max(t, aisle_free[a]) if blocking else t
            wait += entry - t
            if blocking:
                aisle_free[a] = entry + d
            if i + 1 < len(B[b]["visits"]):
                active[b] = i + 1
                p.update(i=i + 1, t=entry + d + B[b]["walks"][i + 1], stamp=stamp)
            else:
                del active[b]
                comp[b] = entry + d + B[b]["walks"][-1]
                p.update(kind="free", b=None, t=comp[b], stamp=stamp)
        stamp += 1
    return comp, start, wait


def test_simulation_agrees_with_a_second_simulation():
    rng = random.Random(8)
    for _ in range(12):
        cfg = Cfg(n_aisles=rng.randint(4, 10), n_pickers=rng.randint(2, 8), n_orders=rng.randint(20, 60), tau=rng.choice([0.4, 0.8, 1.6]), express_share=rng.choice([0.05, 0.25]), hot_corr=rng.choice([0.0, 1.0]))
        inst = make_instance(cfg, rng.randrange(10000))
        for policy, w in (("fifo", 1), ("edd", 1), ("edd_w", rng.choice([2, 4, 8]))):
            for blocking in (True, False):
                r = simulate(inst, policy=policy, w=w, blocking=blocking)
                assert (r["comp"], r["start"], r["wait"]) == _other_simulation(inst, cfg.n_pickers, policy, w, blocking)


def test_s_shape_route_by_hand():
    """Gänge 1, 3 und 5 (ungerade Anzahl): die ersten beiden werden ganz durchquert, der letzte ist Sackgasse (Hin- und Rückweg zur tiefsten Position)."""
    cfg = Cfg()
    route = build_route([(1, 10.0), (1, 20.0), (3, 5.0), (5, 12.0)], cfg)
    walk = lambda a: int(round(a * cfg.aisle_sp / cfg.speed * 10))                              # noqa: E731
    full = int(round((cfg.aisle_len / cfg.speed + 2 * cfg.t_pick) * 10))
    full1 = int(round((cfg.aisle_len / cfg.speed + cfg.t_pick) * 10))
    dead_end = int(round((2 * 12.0 / cfg.speed + cfg.t_pick) * 10))
    assert route["visits"] == [(1, full), (3, full1), (5, dead_end)]
    assert route["walks"] == [walk(1), walk(2), walk(2), walk(5)]
    assert route["D"] == full + full1 + dead_end + walk(1) + 2 * walk(2) + walk(5)


def test_share_of_express_positions_in_hot_aisles_at_rho_zero():
    """Aus den Gewichten exp(-0,15 a) (8 Gänge, 3 heiße): 51,9 % -> README sagt 'rund 52 %'."""
    weights = [math.exp(-0.15 * a) for a in range(8)]
    expected = sum(weights[:3]) / sum(weights)
    assert round(expected * 100) == 52
    hot = total = 0
    for seed in range(40):
        for order in make_instance(Cfg(hot_corr=0.0, express_share=0.5, n_orders=100), seed)["orders"]:
            if order["express"]:
                for a, _ in order["items"]:
                    total += 1
                    hot += a < 3
    assert hot / total == pytest.approx(expected, abs=0.02)
