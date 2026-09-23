"""Instanz, Batching und Route der Wellenfreigabe-Demo (Kommissionierwellen mit Fristen und Gangblockaden).

UNVERAENDERT uebernommen aus lager-planung/messreihe_wellen_konflikt/wellen.py (dort gegen 7 Checks und die
exakte Referenz verifiziert) - nicht neu schreiben. Parallelgang-Lager (Depot vorn links), Batches stehen fest
(Greedy-Seed-Batching nach Gang-Aehnlichkeit, OHNE Fristen). Route je Batch = S-Shape (jeder Gang mit Positionen
wird ganz durchquert, bei ungerader Gangzahl der letzte als Sackgasse). Alle Zeiten ganzzahlig in Dezisekunden,
damit Simulation und CP-SAT-Modell exakt dieselbe Rechnung machen. Nur Standardbibliothek."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

DS = 10  # Dezisekunden je Sekunde


@dataclass(frozen=True)
class Cfg:
    n_aisles: int = 8
    aisle_len: float = 30.0
    aisle_sp: float = 3.0
    speed: float = 1.3
    t_pick: float = 8.0
    capacity: int = 15          # Positionen je Batch
    n_orders: int = 60
    items_min: int = 2
    items_max: int = 6
    hot_aisles: int = 3         # die vordersten Gaenge (nah am Depot) sind "heiss"
    express_share: float = 0.25
    hot_corr: float = 0.8       # rho: Anteil der Express-Positionen, die aus heissen Gaengen kommen
    tau: float = 0.8            # Fristendruck (kleiner = enger)
    n_pickers: int = 4
    express_weight: int = 3


def _d(x: float) -> int:
    return int(round(x * DS))


def _d1(x: float) -> int:
    return max(1, _d(x))


def greedy_seed_batching(orders: list[dict], capacity: int) -> list[list[int]]:
    """Seed = frueheste unzugeordnete Bestellung; dann die Bestellung mit den wenigsten NEUEN Gaengen (bei
    Gleichstand mehr Ueberlappung), bis die Kapazitaet voll ist. Fristen spielen hier bewusst keine Rolle."""
    unassigned = list(range(len(orders)))
    batches: list[list[int]] = []
    aisles_of = [set(a for a, _ in o["items"]) for o in orders]
    while unassigned:
        seed = unassigned.pop(0)
        members = [seed]
        load = len(orders[seed]["items"])
        aisles = set(aisles_of[seed])
        while True:
            best = None
            for o in unassigned:
                n = len(orders[o]["items"])
                if load + n > capacity:
                    continue
                key = (len(aisles_of[o] - aisles), -len(aisles_of[o] & aisles), o)
                if best is None or key < best[0]:
                    best = (key, o)
            if best is None:
                break
            o = best[1]
            unassigned.remove(o)
            members.append(o)
            load += len(orders[o]["items"])
            aisles |= aisles_of[o]
        batches.append(members)
    return batches


def build_route(items: list[tuple[int, float]], cfg: Cfg) -> dict:
    """S-Shape: aufsteigende Gaenge, alternierende Richtung; ungerade Anzahl -> letzter Gang Sackgasse."""
    per: dict[int, list[float]] = {}
    for a, depth in items:
        per.setdefault(a, []).append(depth)
    order = sorted(per)
    n = len(order)
    visits = []
    for k, a in enumerate(order):
        picks = len(per[a])
        if k == n - 1 and n % 2 == 1:
            dur = _d1(2 * max(per[a]) / cfg.speed + picks * cfg.t_pick)
        else:
            dur = _d1(cfg.aisle_len / cfg.speed + picks * cfg.t_pick)
        visits.append((a, dur))
    walks = [_d(order[0] * cfg.aisle_sp / cfg.speed)]
    for k in range(1, n):
        walks.append(_d((order[k] - order[k - 1]) * cfg.aisle_sp / cfg.speed))
    walks.append(_d(order[-1] * cfg.aisle_sp / cfg.speed))  # Rueckweg zum Depot (endet immer vorn)
    return dict(visits=visits, walks=walks, aisles=set(order), D=sum(d for _, d in visits) + sum(walks))


def make_instance(cfg: Cfg, seed: int, k: int | None = None) -> dict:
    rng = random.Random(seed)
    A = cfg.n_aisles
    base_w = [math.exp(-0.15 * a) for a in range(A)]
    orders = []
    for _ in range(cfg.n_orders):
        express = rng.random() < cfg.express_share
        items = []
        for _ in range(rng.randint(cfg.items_min, cfg.items_max)):
            if express and rng.random() < cfg.hot_corr:
                a = rng.randrange(min(cfg.hot_aisles, A))
            else:
                a = rng.choices(range(A), weights=base_w)[0]
            items.append((a, rng.uniform(0, cfg.aisle_len)))
        orders.append(dict(express=express, items=items))
    groups = greedy_seed_batching(orders, cfg.capacity)
    batches = []
    for members in groups:
        route = build_route([it for o in members for it in orders[o]["items"]], cfg)
        route["members"] = members
        batches.append(route)
    K = k if k is not None else cfg.n_pickers
    t_est = sum(b["D"] for b in batches) / K
    rng2 = random.Random(seed * 7919 + 1)
    order_info = {}
    for bi, b in enumerate(batches):
        for o in b["members"]:
            f = rng2.uniform(0.15, 0.5) if orders[o]["express"] else rng2.uniform(0.6, 1.4)
            order_info[o] = (bi, int(cfg.tau * t_est * f), cfg.express_weight if orders[o]["express"] else 1)
    for bi, b in enumerate(batches):
        b["due"] = min(order_info[o][1] for o in b["members"])
    return dict(cfg=cfg, orders=orders, batches=batches, order_info=order_info, K=K)
