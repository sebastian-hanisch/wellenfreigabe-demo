"""Preset-Abstimmung: traegt die Geschichte jedes Presets (Detailplan plan_wellen_konflikt.html, Abschnitt 7) gegen die
Abnahmekriterien in wfg_stories.py?

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/tune_presets.py [--seeds]

Die Kriterien stehen auf der 80-Instanzen-Population (Seeds 0..79), alles deterministisch - ein Lauf je Preset
genuegt. Die Fachmodell-Konstanten (Ganglaenge, Kapazitaet, heisse Gaenge, Express-Gewicht) sind FEST; je Preset
variieren nur die Regler. Mit --seeds wird zusaetzlich fuer jedes Preset ein REPRAESENTATIVER Anzeige-Seed gesucht
(Seeds 100..399, also ausserhalb der Stichprobe): die gezeigte Einzelinstanz soll in Wartezeitanteil und Verspaetung
nahe am Populationsmittel liegen, damit das Gantt die Geschichte des Presets nicht per Zufall widerlegt.
Keine Wall-Clock-Loeser (CP-SAT) in diesem Werkzeug."""
import statistics as st
import sys

sys.path.insert(0, ".")
import wfg_constants as C
import wfg_evaluation as E
import wfg_stories as ST


def preset_cfg(p):
    return E.cfg_from_controls(p["aisles"], p["pickers"], p["orders"], p["tau"], p["express_pct"], p["hot_corr_pct"])


def representative_seeds(cfg, w, pop, lo=100, hi=400, top=3):
    """Seeds ausserhalb der Stichprobe mit Wartezeitanteil und Verspaetung (EDD-w) nahe dem Populationsmittel."""
    target_wait = pop.wait_share_pct(C.RULE_EDDW)
    target_obj = pop.mean_min(C.RULE_EDDW)
    obj_scale = st.pstdev(pop.obj[C.RULE_EDDW]) / C.MIN_DS or 1.0
    scored = []
    for seed in range(lo, hi):
        inst, res = E.shown_run(cfg, seed, C.RULE_EDDW, w)
        s = E.shown_summary(inst, res)
        score = abs(s["wait_share_pct"] - target_wait) / max(target_wait, 1.0) + abs(s["obj_min"] - target_obj) / obj_scale
        scored.append((score, seed, s))
    scored.sort()
    return scored[:top]


def main():
    all_ok = True
    for name, p in C.PRESETS.items():
        cfg = preset_cfg(p)
        pop = E.evaluate_population(cfg, p["window"])
        metrics = ST.metrics_from_population(pop)
        g = pop.gain()
        print(f"\n### {name}  {p}")
        print(f"  EDD {pop.mean_min('edd'):.1f} (ohne Blockieren {pop.mean_min('edd_free'):.1f})  Fenster w={p['window']} "
              f"{pop.mean_min('edd_w'):.1f}  Wartezeitanteil {pop.wait_share_pct('edd'):.1f} %  "
              f"Vorteil EDD an {metrics.adv_on.mean:.1f} aus {metrics.adv_off.mean:.1f}  "
              f"Gewinn {g.mean:+.1f} +- {g.se:.1f}  Batches {pop.n_batches:.1f}")
        for ok, text in ST.criteria(name, metrics):
            print(("  OK   " if ok else "  FAIL ") + text)
            all_ok = all_ok and ok
        inst, res = E.shown_run(cfg, p["seed"], C.RULE_EDDW, p["window"])
        s = E.shown_summary(inst, res)
        print(f"  gezeigter Seed {p['seed']}: Wartezeitanteil {s['wait_share_pct']:.1f} %, Verspaetung {s['obj_min']:.1f} Min., "
              f"{s['n_batches']} Batches (Population: {pop.wait_share_pct('edd_w'):.1f} %, {pop.mean_min('edd_w'):.1f} Min.)")
        if "--seeds" in sys.argv:
            for score, seed, s in representative_seeds(cfg, p["window"], pop):
                print(f"    Kandidat Seed {seed}: Wartezeitanteil {s['wait_share_pct']:.1f} %, "
                      f"Verspaetung {s['obj_min']:.1f} Min. (Abstand {score:.3f})")
    print("\nalle Kriterien erfuellt" if all_ok else "\nMINDESTENS EIN KRITERIUM VERFEHLT - Presets nachschaerfen")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
