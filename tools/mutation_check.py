"""Fehler-Einbau-Test: baut einzelne Fehler in die Module ein und prueft, ob die Tests (ohne AppTests, die sind zu
langsam fuer viele Mutanten) sie finden.

Aufruf (im Projektordner): ./venv/Scripts/python.exe tools/mutation_check.py [Teilstring des Dateinamens] [--jobs N]
Jeder Mutant ersetzt genau eine Stelle; Ueberlebende sind entweder gleichwertig (kein sichtbarer Unterschied) oder eine
Luecke der Tests. Jeder Mutant laeuft in einer eigenen temporaeren Kopie (deshalb parallel moeglich, Standard 6 Jobs);
PYTHONDONTWRITEBYTECODE=1, damit veralteter Bytecode keine Ueberlebenden vortaeuscht; Quelltexte als LF (Windows-Python
schreibt sonst CRLF und die Zeichenketten unten finden nichts). Der langsame CP-Referenztest (Beweislaeufe mit Zeitlimit)
laeuft nur fuer Mutanten in wfg_cp.py; die Handinstanz-Tests des CP-Modells laufen immer."""
import concurrent.futures as cf
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
TIMEOUT = 300
SLOW = "tests/test_core_checks.py::test_cp_reference_is_never_beaten_by_a_heuristic"

MUTANTS = [
    # wfg_scenario.py: Batching, S-Shape-Route, Instanz, Fristen
    ("wfg_scenario.py", "-len(aisles_of[o] & aisles), o)", "len(aisles_of[o] & aisles), o)"),
    ("wfg_scenario.py", "if load + n > capacity:", "if load + n >= capacity:"),
    ("wfg_scenario.py", "if k == n - 1 and n % 2 == 1:", "if k == n - 1 and n % 2 == 0:"),
    ("wfg_scenario.py", "dur = _d1(2 * max(per[a]) / cfg.speed + picks * cfg.t_pick)", "dur = _d1(max(per[a]) / cfg.speed + picks * cfg.t_pick)"),
    ("wfg_scenario.py", "walks.append(_d(order[-1] * cfg.aisle_sp / cfg.speed))", "walks.append(_d(order[0] * cfg.aisle_sp / cfg.speed))"),
    ("wfg_scenario.py", "math.exp(-0.15 * a)", "math.exp(-0.30 * a)"),
    ("wfg_scenario.py", "if express and rng.random() < cfg.hot_corr:", "if express or rng.random() < cfg.hot_corr:"),
    ("wfg_scenario.py", "rng.randrange(min(cfg.hot_aisles, A))", "rng.randrange(A)"),
    ("wfg_scenario.py", "t_est = sum(b[\"D\"] for b in batches) / K", "t_est = sum(b[\"D\"] for b in batches) / (K + 1)"),
    ("wfg_scenario.py", "rng2.uniform(0.15, 0.5) if", "rng2.uniform(0.25, 0.5) if"),
    ("wfg_scenario.py", "cfg.express_weight if orders[o][\"express\"] else 1)", "cfg.express_weight if orders[o][\"express\"] else 2)"),
    ("wfg_scenario.py", "b[\"due\"] = min(order_info[o][1] for o in b[\"members\"])", "b[\"due\"] = max(order_info[o][1] for o in b[\"members\"])"),
    # wfg_sim.py: Regeln, Ereignissimulation, Zielfunktion
    ("wfg_sim.py", "return min(waiting)", "return max(waiting)"),
    ("wfg_sim.py", "cand = sorted(waiting, key=lambda b: (B[b][\"due\"], b))", "cand = sorted(waiting, key=lambda b: (B[b][\"due\"], -b))"),
    ("wfg_sim.py", "cand = cand[:max(1, w)]", "cand = cand[:max(1, w - 1)]"),
    ("wfg_sim.py", "B[ab][\"visits\"][i:]", "B[ab][\"visits\"][i + 1:]"),
    ("wfg_sim.py", "len(B[b][\"aisles\"] & rem)", "len(B[b][\"aisles\"] | rem)"),
    ("wfg_sim.py", "key=lambda b: (conflict(b), B[b][\"due\"], b))", "key=lambda b: (conflict(b), -B[b][\"due\"], b))"),
    ("wfg_sim.py", "entry = max(t, aisle_free[aisle]) if blocking else t", "entry = min(t, aisle_free[aisle]) if blocking else t"),
    ("wfg_sim.py", "aisle_free[aisle] = exit_", "aisle_free[aisle] = entry"),
    ("wfg_sim.py", "wait_total += entry - t", "wait_total += entry"),
    ("wfg_sim.py", "(t + B[b][\"walks\"][0], seq, \"arrive\", p)", "(t, seq, \"arrive\", p)"),
    ("wfg_sim.py", "end = exit_ + B[b][\"walks\"][-1]", "end = exit_"),
    ("wfg_sim.py", "tard = max(0, comp[bi] - due)", "tard = comp[bi] - due"),
    ("wfg_sim.py", "obj += wt * tard", "obj += tard"),
    ("wfg_sim.py", "late += 1 if tard > 0 else 0", "late += 1 if tard >= 0 else 0"),
    ("wfg_sim.py", "makespan=max(comp)", "makespan=min(comp)"),
    # wfg_cp.py: Groessenpruefung und CP-Modell
    ("wfg_cp.py", "and len(inst[\"orders\"]) <= C.EXACT_MAX_ORDERS", "or len(inst[\"orders\"]) <= C.EXACT_MAX_ORDERS"),
    ("wfg_cp.py", "len(inst[\"batches\"]) <= C.EXACT_MAX_BATCHES", "len(inst[\"batches\"]) < C.EXACT_MAX_BATCHES"),
    ("wfg_cp.py", "        for ivs in aisle_iv.values():\n            m.AddNoOverlap(ivs)", "        for ivs in aisle_iv.values():\n            pass"),
    ("wfg_cp.py", "m.AddCumulative(batch_iv, [1] * len(B), K)", "m.AddCumulative(batch_iv, [1] * len(B), K + 1)"),
    ("wfg_cp.py", "m.Add(t >= E[bi] - due)", "m.Add(t >= E[bi] - due - 1)"),
    ("wfg_cp.py", "terms.append(wt * t)", "terms.append(t)"),
    # wfg_evaluation.py: Statistik, Urteil, Meldung, Sweeps, Exakt-Zusammenfassung
    ("wfg_evaluation.py", "if self.mean > se_factor * self.se:", "if self.mean >= se_factor * self.se:"),
    ("wfg_evaluation.py", "if self.mean < -se_factor * self.se:", "if self.mean <= -se_factor * self.se:"),
    ("wfg_evaluation.py", "(st.stdev(diffs) / len(diffs) ** 0.5) / C.MIN_DS", "(st.stdev(diffs) / len(diffs)) / C.MIN_DS"),
    ("wfg_evaluation.py", "on = [f - e for f, e in zip(self.obj[C.RULE_FIFO], self.obj[C.RULE_EDD])]", "on = [e - f for f, e in zip(self.obj[C.RULE_FIFO], self.obj[C.RULE_EDD])]"),
    ("wfg_evaluation.py", "return self.pair(C.RULE_EDD, C.RULE_EDDW)", "return self.pair(C.RULE_EDDW, C.RULE_EDD)"),
    ("wfg_evaluation.py", "return self.pair(rule, C.RULE_EDD)", "return self.pair(C.RULE_EDD, rule)"),
    ("wfg_evaluation.py", "return self.pair(\"fifo_free\", \"edd_free\")", "return self.pair(\"edd_free\", \"fifo_free\")"),
    ("wfg_evaluation.py", "if wait_share_pct < C.WAIT_SHARE_LOW_PCT:", "if wait_share_pct <= C.WAIT_SHARE_LOW_PCT:"),
    ("wfg_evaluation.py", "return (on - off) / off * 100.0 if off else 0.0", "return (off - on) / off * 100.0 if off else 0.0"),
    ("wfg_evaluation.py", "wait[key] = st.fmean(r[\"wait\"] / (r[\"work\"] + r[\"wait\"]) for r in rs) * 100.0", "wait[key] = st.fmean(r[\"wait\"] / r[\"work\"] for r in rs) * 100.0"),
    ("wfg_evaluation.py", "express_share=int(express_pct) / 100.0", "express_share=int(express_pct) / 10.0"),
    ("wfg_evaluation.py", "c = replace(cfg, hot_corr=rho / 100.0)", "c = replace(cfg, hot_corr=rho / 10.0)"),
    ("wfg_evaluation.py", "replace(cfg, n_pickers=int(k))", "replace(cfg, n_pickers=cfg.n_pickers)"),
    ("wfg_evaluation.py", "return dict(policy=\"edd_w\", w=int(w))", "return dict(policy=\"edd_w\", w=int(w) + 1)"),
    ("wfg_evaluation.py", "potential_pct=pct(edd - opt[\"obj\"], edd)", "potential_pct=pct(opt[\"obj\"] - edd, edd)"),
    ("wfg_evaluation.py", "price_pct=pct(opt[\"obj\"] - opt_free[\"obj\"], opt_free[\"obj\"])", "price_pct=pct(opt[\"obj\"] - opt_free[\"obj\"], opt[\"obj\"])"),
    ("wfg_evaluation.py", "proven = opt[\"status\"] == \"OPTIMAL\"", "proven = opt[\"status\"] != \"OPTIMAL\""),
    ("wfg_evaluation.py", "return st.fmean(self.late[key]) / self.cfg.n_orders * 100.0", "return st.fmean(self.late[key]) / self.cfg.n_orders"),
    ("wfg_evaluation.py", "counts[pair.verdict()] += 1", "counts[\"none\"] += 1"),
    ("wfg_evaluation.py", "makespan_min=result[\"makespan\"] / C.MIN_DS", "makespan_min=result[\"makespan\"]"),
    # wfg_presets.py: Permalink
    ("wfg_presets.py", "value = max(spec.lo, value)", "value = value"),
    ("wfg_presets.py", "if spec.hi is not None:\n        value = min(spec.hi, value)", "if spec.hi is not None:\n        value = value"),
    ("wfg_presets.py", "spec.lo + round((value - spec.lo) / spec.step) * spec.step", "spec.lo + int((value - spec.lo) / spec.step) * spec.step"),
    ("wfg_presets.py", "value = round(value, 6)", "value = value"),
    # wfg_stories.py: Schwellen der Presets
    ("wfg_stories.py", "m.wait_share_pct >= 10.0", "m.wait_share_pct >= 9.0"),
    ("wfg_stories.py", "ratio >= 1.5", "ratio >= 1.4"),
    ("wfg_stories.py", "(m.gain.verdict() == \"pos\",\n                 f\"Gewinn des Fensters positiv", "(m.gain.mean > 0,\n                 f\"Gewinn des Fensters positiv"),
    ("wfg_stories.py", "m.wait_share_pct <= 6.0", "m.wait_share_pct <= 7.0"),
    ("wfg_stories.py", "rel <= 0.05", "rel <= 0.06"),
    ("wfg_stories.py", "abs(m.adv_on.mean - m.adv_off.mean)", "(m.adv_on.mean - m.adv_off.mean)"),
    ("wfg_stories.py", "(m.gain.verdict() == \"neg\",\n                 f\"Gewinn des Fensters negativ", "(m.gain.mean < 0,\n                 f\"Gewinn des Fensters negativ"),
    ("wfg_stories.py", "m.wait_share_pct >= 25.0", "m.wait_share_pct >= 24.0"),
    ("wfg_stories.py", "share <= 0.5", "share <= 0.6"),
    ("wfg_stories.py", "m.gain.mean >= 10.0 and m.gain.verdict() == \"pos\"", "m.gain.mean >= 9.0 and m.gain.verdict() == \"pos\""),
    ("wfg_stories.py", "m.gain.mean >= 10.0 and m.gain.verdict() == \"pos\"", "m.gain.mean >= 10.0"),
    ("wfg_stories.py", "m.gain.mean <= -20.0 and m.gain.verdict() == \"neg\"", "m.gain.mean <= -19.0 and m.gain.verdict() == \"neg\""),
    ("wfg_stories.py", "m.gain.mean <= -20.0 and m.gain.verdict() == \"neg\"", "m.gain.mean <= -20.0"),
    # wfg_visualization.py: Konsistenz der Grafiken
    ("wfg_visualization.py", "opacity=[1.0 if p.verdict() != \"none\" else 0.35 for p in pairs]", "opacity=[1.0 if p.verdict() == \"pos\" else 0.35 for p in pairs]"),
    ("wfg_visualization.py", "busy_col.append(C.BATCH_COLORS[batch % len(C.BATCH_COLORS)])", "busy_col.append(C.BATCH_COLORS[0])"),
    ("wfg_visualization.py", "if entry > arrive:", "if entry >= arrive:"),
    ("wfg_visualization.py", "return \"±0 %\" if text in (\"+0\", \"-0\")", "return \"±0 %\" if text in (\"+0\",)"),
    # wfg_pdf_export.py: Sonderzeichen
    ("wfg_pdf_export.py", "\"−\": \"-\"", "\"−\": \"~\""),
    ("wfg_pdf_export.py", "\"€\": \"EUR\"", "\"€\": \"E\""),
]


def run_one(n, name, old, new, tmp_root, only):
    """Ein Mutant in eigener Kopie; Rueckgabe (n, name, old, new, Status)."""
    work = pathlib.Path(tempfile.mkdtemp(prefix=f"wfg_mut{n}_", dir=tmp_root))
    try:
        for f in ROOT.glob("*.py"):
            (work / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
        for extra in ("README.md",):                       # test_claims.py liest das README
            if (ROOT / extra).exists():
                shutil.copy(ROOT / extra, work / extra)
        shutil.copytree(ROOT / "tests", work / "tests", ignore=shutil.ignore_patterns("__pycache__"))
        for f in (work / "tests").rglob("*.py"):
            f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
        path = work / name
        original = path.read_bytes().decode("utf-8")
        if original.count(old) != 1:
            return n, name, old, new, f"FEHLER:{original.count(old)}"
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        args = [PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests", "--ignore=tests/test_app.py"]
        if name != "wfg_cp.py":
            args.append(f"--deselect={SLOW}")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        try:
            r = subprocess.run(args, cwd=work, env=env, capture_output=True, text=True, timeout=TIMEOUT)
            return n, name, old, new, "UEBERLEBT" if r.returncode == 0 else "gefunden"
        except subprocess.TimeoutExpired:
            return n, name, old, new, "gefunden(Zeitueberschreitung)"     # Endlosschleife gilt als gefunden
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    jobs = 6
    for i, a in enumerate(sys.argv[1:]):
        if a == "--jobs":
            jobs = int(sys.argv[i + 2])
            args = [x for x in args if x != sys.argv[i + 2]]
    only = args[0] if args else ""
    tmp_root = tempfile.mkdtemp(prefix="wfg_mut_")
    # Selbstpruefung des Werkzeugs: ein Mutant, der nichts aendert, MUSS ueberleben. Sonst scheitern die Tests schon
    # in der Kopie (fehlende Datei, Umgebung), und jeder "gefundene" Mutant waere vorgetaeuscht.
    for probe in ("wfg_sim.py", "wfg_cp.py"):
        status = run_one(0, probe, "import wfg_constants as C" if probe == "wfg_cp.py" else "import heapq", 
                         "import wfg_constants as C" if probe == "wfg_cp.py" else "import heapq", tmp_root, only)[4]
        if status != "UEBERLEBT":
            print(f"ABBRUCH: unveraenderte Kopie besteht die Tests nicht ({probe}: {status}) - Ergebnisse waeren wertlos")
            shutil.rmtree(tmp_root, ignore_errors=True)
            return 2
    print("Selbstpruefung: unveraenderte Kopie besteht alle Tests (Werkzeug funktioniert)", flush=True)
    todo = [(n, *m) for n, m in enumerate(MUTANTS, 1) if not only or only in m[0]]
    survivors, errors, killed = [], [], 0
    with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [pool.submit(run_one, n, name, old, new, tmp_root, only) for n, name, old, new in todo]
        for fut in cf.as_completed(futures):
            n, name, old, new, status = fut.result()
            if status.startswith("FEHLER"):
                errors.append((n, name, old[:60], status))
                print(f"[{n:3d}] FEHLER (Stelle nicht eindeutig: {status})  {name}: {old[:60]!r}", flush=True)
            elif status == "UEBERLEBT":
                survivors.append((n, name, old[:70], new[:70]))
                print(f"[{n:3d}] UEBERLEBT  {name}: {old[:60]!r} -> {new[:60]!r}", flush=True)
            else:
                killed += 1
                print(f"[{n:3d}] {status}  {name}", flush=True)
    print(f"\n{killed} gefunden, {len(survivors)} ueberlebt, {len(errors)} Fehler in der Mutantenliste (von {len(todo)})")
    shutil.rmtree(tmp_root, ignore_errors=True)
    return 1 if (survivors or errors) else 0


if __name__ == "__main__":
    sys.exit(main())
