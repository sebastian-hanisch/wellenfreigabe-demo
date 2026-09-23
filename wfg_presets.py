"""Regler-Spezifikation, Permalink, Presets und Seed-Knopf (Standardmuster aus dem OR-Demo-Portfolio, siehe
rrs_presets.py in routenresilienz-demo). Alle Regler sind Zahlen; Prozent-Regler in GANZZAHLIGEN Prozentpunkten,
der Fristendruck in Zehnteln - beim Permalink wird jeder Wert auf den Bereich begrenzt UND auf die Reglerstufe
eingerastet, damit die Adresszeile nie einen Wert ausserhalb des Rasters in den Regler schreibt."""
import math
import random
from dataclasses import dataclass
from typing import Callable, Optional

import streamlit as st

import wfg_constants as C


def _int_text(value):
    return str(int(value))


def _tau_text(value):
    return f"{float(value):.1f}"


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: Callable
    default: object
    lo: Optional[float] = None
    hi: Optional[float] = None
    step: Optional[float] = None
    encoder: Callable = _int_text


SETTING_SPECS = {
    "aisles_slider": SettingSpec("a", int, C.AISLES_DEFAULT, *C.AISLES_RANGE, 1),
    "pickers_slider": SettingSpec("k", int, C.PICKERS_DEFAULT, *C.PICKERS_RANGE, 1),
    "orders_slider": SettingSpec("n", int, C.ORDERS_DEFAULT, *C.ORDERS_RANGE, 1),
    "tau_slider": SettingSpec("tau", float, C.TAU_DEFAULT, *C.TAU_RANGE, C.TAU_STEP, encoder=_tau_text),
    "express_slider": SettingSpec("ex", int, C.EXPRESS_PCT_DEFAULT, *C.EXPRESS_PCT_RANGE, 1),
    "hot_corr_slider": SettingSpec("rho", int, C.HOT_CORR_PCT_DEFAULT, *C.HOT_CORR_PCT_RANGE, C.HOT_CORR_STEP),
    "window_slider": SettingSpec("w", int, C.WINDOW_DEFAULT, *C.WINDOW_RANGE, 1),
    "seed_input": SettingSpec("seed", int, C.SEED_DEFAULT, *C.SEED_RANGE, 1),
}

PRESET_STATE_KEYS = {
    "aisles": "aisles_slider", "pickers": "pickers_slider", "orders": "orders_slider", "tau": "tau_slider",
    "express_pct": "express_slider", "hot_corr_pct": "hot_corr_slider", "window": "window_slider",
    "seed": "seed_input",
}


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def parse_setting(spec, raw):
    """Wert aus der Adresszeile: umwandeln, auf den Bereich begrenzen, auf die Reglerstufe einrasten. None, wenn er
    sich nicht auswerten laesst (kein Zahlenwert, nicht endlich)."""
    try:
        value = spec.caster(raw)
    except (ValueError, TypeError):
        try:                                    # "12.0" fuer einen Ganzzahl-Regler
            value = spec.caster(float(raw))
        except (ValueError, TypeError, OverflowError):
            return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    if spec.step and spec.lo is not None and spec.step != 1:
        value = spec.lo + round((value - spec.lo) / spec.step) * spec.step
        value = min(spec.hi, value)
        if isinstance(spec.step, float) or isinstance(spec.lo, float):
            value = round(value, 6)
    return spec.caster(value) if spec.caster is int else value


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            value = parse_setting(spec, qp[spec.url_param])
            if value is not None:
                st.session_state[state_key] = value
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """values: dict state_key -> aktueller Wert (aus den Widgets)."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = SETTING_SPECS[state_key].encoder(value)
    except Exception:
        pass


def apply_preset(name):
    for field, state_key in PRESET_STATE_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][field]


def randomize_seed():
    """Wuerfelt einen neuen Seed fuer die gezeigte Instanz."""
    st.session_state["seed_input"] = random.randint(*C.SEED_RANGE)
