"""Regler: Permalink-Parsing/-Klemmen/-Einrasten, Presets innerhalb ihrer eigenen Grenzen."""
import wfg_constants as C
from wfg_presets import PRESET_STATE_KEYS, SETTING_SPECS, SettingSpec, bounds, parse_setting


def test_numeric_setting_is_clamped_to_its_range():
    spec = SETTING_SPECS["aisles_slider"]
    assert parse_setting(spec, "999") == spec.hi
    assert parse_setting(spec, "-5") == spec.lo
    assert parse_setting(SETTING_SPECS["pickers_slider"], "1") == C.PICKERS_RANGE[0]      # Minimum 2


def test_integer_setting_accepts_float_text_and_rejects_garbage():
    spec = SETTING_SPECS["orders_slider"]
    assert parse_setting(spec, "45.0") == 45 and isinstance(parse_setting(spec, "45.0"), int)
    assert parse_setting(spec, "abc") is None and parse_setting(spec, "") is None


def test_non_finite_values_are_rejected():
    for key in ("tau_slider", "aisles_slider", "seed_input"):
        assert parse_setting(SETTING_SPECS[key], "nan") is None
        assert parse_setting(SETTING_SPECS[key], "inf") is None


def test_tau_is_snapped_to_tenths_and_clamped():
    spec = SETTING_SPECS["tau_slider"]
    assert parse_setting(spec, "0.87") == 0.9
    assert parse_setting(spec, "0.83") == 0.8
    assert parse_setting(spec, "0.1") == C.TAU_RANGE[0] == 0.4
    assert parse_setting(spec, "9") == C.TAU_RANGE[1] == 2.0
    assert parse_setting(spec, "1.6") == 1.6                       # exakt auf dem Raster (Float-Rundung!)


def test_hot_corr_is_snapped_to_steps_of_five():
    spec = SETTING_SPECS["hot_corr_slider"]
    assert parse_setting(spec, "83") == 85 and parse_setting(spec, "81") == 80
    assert parse_setting(spec, "0") == 0 and parse_setting(spec, "100") == 100 and parse_setting(spec, "250") == 100
    assert isinstance(parse_setting(spec, "83"), int)


def test_express_minimum_is_five_percent():
    assert parse_setting(SETTING_SPECS["express_slider"], "0") == 5
    assert bounds("express_slider") == (5, 50)


def test_url_params_are_unique_and_defaults_inside_bounds():
    assert len({spec.url_param for spec in SETTING_SPECS.values()}) == len(SETTING_SPECS)
    for key, spec in SETTING_SPECS.items():
        assert spec.lo <= spec.default <= spec.hi, key
        assert spec.encoder(spec.default)


def test_encoders_roundtrip_through_parse():
    for key, spec in SETTING_SPECS.items():
        assert parse_setting(spec, spec.encoder(spec.default)) == spec.default, key
    assert SETTING_SPECS["tau_slider"].encoder(0.8) == "0.8"


def test_defaults_equal_the_standard_preset():
    for field, state_key in PRESET_STATE_KEYS.items():
        assert SETTING_SPECS[state_key].default == C.PRESETS["Standard"][field], field


def test_every_preset_is_within_its_own_widget_bounds():
    for name, cfg in C.PRESETS.items():
        for field, state_key in PRESET_STATE_KEYS.items():
            spec = SETTING_SPECS[state_key]
            assert spec.lo <= cfg[field] <= spec.hi, (name, field)
        # rasterkonform (sonst schreibt das Preset einen Wert zwischen zwei Reglerstufen)
        assert parse_setting(SETTING_SPECS["tau_slider"], str(cfg["tau"])) == cfg["tau"], name
        assert parse_setting(SETTING_SPECS["hot_corr_slider"], str(cfg["hot_corr_pct"])) == cfg["hot_corr_pct"], name


def test_preset_seeds_are_outside_the_population_seeds():
    """Die gezeigte Instanz (Gantt) liegt bewusst ausserhalb der Stichprobe-Seeds 0..79."""
    assert C.SEED_DEFAULT >= C.N_POPULATION
    assert all(p["seed"] >= C.N_POPULATION for p in C.PRESETS.values())


def test_preset_names_are_short_enough_for_a_button_label_and_have_help():
    assert all(len(name) <= 32 for name in C.PRESETS)
    assert set(C.PRESET_HELP) == set(C.PRESETS)


def test_there_are_exactly_five_presets_arranged_three_plus_two():
    assert len(C.PRESETS) == 5
    assert list(C.PRESETS)[:3] == ["Standard", "Wenige Kommissionierer", "Viele Kommissionierer"]


def test_setting_spec_defaults_use_int_text_for_integers():
    assert SettingSpec("x", int, 3).encoder(3.0) == "3"


def test_tau_grid_is_free_of_float_noise():
    """0,4 + k x 0,1 liefert bei k = 2, 3, 8, 13, 14 Rauschen (0,6000000000000001 ...): das Einrasten muss auf die Reglerstufe
    zuruckrunden, sonst schreibt die Adresszeile einen Wert neben die Stufe in den Regler."""
    spec = SETTING_SPECS["tau_slider"]
    for k in range(17):
        exact = round(0.4 + k / 10, 1)
        assert parse_setting(spec, f"{exact:.1f}") == exact, k
        assert parse_setting(spec, f"{exact + 0.02:.2f}") == exact, k
