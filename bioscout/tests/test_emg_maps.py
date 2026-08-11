"""Named ``emg_map``s in session.yaml — back-compat, selection, failure modes.

`emg_map` may be ONE flat channel map (the original form) or SEVERAL NAMED
maps that iterations pick from with `emg_map: <name>`. The rules worth pinning
down in tests are: a flat file behaves exactly as it always did, an iteration
gets the map it named, and an ambiguous file FAILS AT LOAD rather than picking
one — a wrong electrode set leaves no trace in the output, so it has to be
caught before anything runs.

    pytest bioscout/tests/test_emg_maps.py
"""

import os
import textwrap

import pytest

from bioscout.utils import session as S


# --------------------------------------------------------------------------
def write(tmp_path, text):
    p = tmp_path / "session.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


FLAT = """\
    subject: A03
    session: '25_03_31'
    body_mass: 89.9
    emg_map:
      EMG01_l: [vaslat_l, vasmed_l]
      EMG09_l: [gasmed_l, gaslat_l]
    iterations:
      cateli: {generic: C.osim, so_model: s.osim, color: green}
      gpk:    {generic: G.osim, so_model: s.osim}
"""

NAMED = """\
    subject: A03
    session: '25_03_31'
    body_mass: 89.9
    emg_map:
      narrow:
        EMG01_l: [vaslat_l, vasmed_l]
        EMG09_l: [gasmed_l, gaslat_l]
      triceps:
        EMG01_l: [vaslat_l, vasmed_l]
        EMG09_l: [gasmed_l, gaslat_l, soleus_l]
      wide:
        EMG01_l: [vaslat_l, vasmed_l]
        EMG09_l: [gasmed_l, gaslat_l, soleus_l, perlong_l]
    iterations:
      cateli_narrow:  {generic: C.osim, emg_map: narrow}
      cateli_triceps: {generic: C.osim, emg_map: triceps}
      gpk_wide:       {generic: G.osim, emg_map: wide}
"""


# --- the flat form is untouched -------------------------------------------
def test_flat_parses_exactly_as_before(tmp_path):
    p = write(tmp_path, FLAT)
    spec = S.read_session_yaml(p)
    assert spec.emg_muscle_mapping == {"EMG01_l": ["vaslat_l", "vasmed_l"],
                                       "EMG09_l": ["gasmed_l", "gaslat_l"]}
    assert spec.emg_muscle_mappings == {}       # a flat file gains no named maps
    assert spec.default_emg_map is None
    cfg = S.load_session_yaml(p)
    assert not S.is_named_emg_map(cfg)
    for it in ("cateli", "gpk"):
        assert S.resolve_emg_map(cfg, it) == spec.emg_muscle_mapping


def test_flat_stays_flat_through_a_rewrite(tmp_path):
    spec = S.read_session_yaml(write(tmp_path, FLAT))
    out = str(tmp_path / "out" / "session.yaml")
    os.makedirs(os.path.dirname(out))
    S.write_session_yaml(spec, out)
    raw = S.load_session_yaml(out)
    assert not S.is_named_emg_map(raw)
    assert "emg_map" not in raw["iterations"]["cateli"]


def test_iterations_as_a_list_still_loads(tmp_path):
    spec = S.read_session_yaml(write(tmp_path, """\
        subject: s1
        emg_map: {EMG01: [vaslat_l]}
        iterations:
          - {name: cateli, generic: C.osim}
    """))
    assert spec.model_names() == ["cateli"]
    assert spec.emg_muscle_mapping == {"EMG01": ["vaslat_l"]}


def test_bare_string_channel_is_split_into_muscles(tmp_path):
    cfg = S.load_session_yaml(write(tmp_path, """\
        emg_map:
          narrow: {EMG01: vaslat_l vasmed_l}
        iterations: {cateli: {}}
    """))
    assert S.resolve_emg_map(cfg, "cateli") == {"EMG01": ["vaslat_l", "vasmed_l"]}


# --- named maps ------------------------------------------------------------
def test_each_iteration_gets_the_map_it_named(tmp_path):
    cfg = S.load_session_yaml(write(tmp_path, NAMED))
    assert S.is_named_emg_map(cfg)
    assert list(S.emg_maps(cfg)) == ["narrow", "triceps", "wide"]
    assert S.resolve_emg_map(cfg, "cateli_narrow")["EMG09_l"] == ["gasmed_l", "gaslat_l"]
    assert S.resolve_emg_map(cfg, "cateli_triceps")["EMG09_l"][-1] == "soleus_l"
    assert S.resolve_emg_map(cfg, "gpk_wide")["EMG09_l"][-1] == "perlong_l"


@pytest.mark.parametrize("iteration,tail", [
    ("cateli_narrow", "gaslat_l"),
    ("cateli_triceps", "soleus_l"),
    ("gpk_wide", "perlong_l"),
])
def test_trial_config_injects_the_selected_map(tmp_path, iteration, tail):
    write(tmp_path, NAMED)
    cfg = S.Iteration(str(tmp_path), iteration).trial_config("Squat_BW_01")
    assert cfg["emg_map"]["EMG09_l"][-1] == tail
    assert cfg["emg_map_name"] == iteration.split("_")[-1]


def test_named_maps_survive_a_rewrite(tmp_path):
    spec = S.read_session_yaml(write(tmp_path, NAMED))
    out = str(tmp_path / "out" / "session.yaml")
    os.makedirs(os.path.dirname(out))
    S.write_session_yaml(spec, out)
    again = S.read_session_yaml(out)
    assert again.emg_muscle_mappings == spec.emg_muscle_mappings
    assert [m.emg_map for m in again.models] == ["narrow", "triceps", "wide"]


@pytest.mark.parametrize("body,expected", [
    # only one map -> no selector needed
    ("emg_map:\n  narrow: {E: [a]}\niterations: {c: {}}\n", "narrow"),
    # a map literally called `default`
    ("emg_map:\n  default: {E: [a]}\n  wide: {E: [a, b]}\niterations: {c: {}}\n",
     "default"),
    # an explicit session-wide default
    ("emg_map:\n  n: {E: [a]}\n  w: {E: [b]}\ndefault_emg_map: w\n"
     "iterations: {c: {}}\n", "w"),
])
def test_silent_iterations_resolve_when_there_is_a_default(tmp_path, body, expected):
    cfg = S.load_session_yaml(write(tmp_path, body))
    assert S.emg_map_name_for(cfg, "c") == expected


def test_an_empty_named_map_means_no_channels_not_fall_back(tmp_path):
    write(tmp_path, """\
        emg_map:
          none:   {}
          narrow: {EMG01: [vaslat_l]}
        iterations:
          bare: {emg_map: none}
    """)
    cfg = S.Iteration(str(tmp_path), "bare").trial_config("T")
    assert cfg["emg_map"] == {}
    assert cfg["emg_map_name"] == "none"


# --- ambiguity and typos are LOAD-TIME errors ------------------------------
@pytest.mark.parametrize("body,needle", [
    # several maps, nothing says which
    (NAMED.replace("{generic: G.osim, emg_map: wide}", "{generic: G.osim}"),
     "does not say which"),
    # the `models:` alias is validated too
    ("emg_map:\n  n: {E: [a]}\n  w: {E: [b]}\nmodels: {c: {generic: C.osim}}\n",
     "does not say which"),
    # nothing to pin a choice to at all
    ("emg_map:\n  n: {E: [a]}\n  w: {E: [b]}\n", "does not say which"),
    # selector names a map that does not exist
    (NAMED.replace("emg_map: wide}", "emg_map: widee}"), "not defined"),
    # selector on a flat map
    (FLAT.replace("{generic: G.osim, so_model: s.osim}",
                  "{generic: G.osim, emg_map: narrow}"), "flat block"),
    # an inline channel map inside an iteration
    ("emg_map:\n  n: {E: [a]}\n  w: {E: [b]}\n"
     "iterations: {c: {emg_map: {E: [a]}}}\n", "must be the NAME"),
    # named maps mixed with bare channels
    ("emg_map:\n  n: {E: [a]}\n  E9: [b]\niterations: {c: {emg_map: n}}\n",
     "mixes named sub-blocks"),
    # names differing only by case (same folder on Windows)
    ("emg_map:\n  Narrow: {E: [a]}\n  narrow: {E: [b]}\n"
     "iterations: {c: {emg_map: narrow}}\n", "differ only"),
    # default_emg_map naming nothing
    ("emg_map:\n  n: {E: [a]}\n  w: {E: [b]}\ndefault_emg_map: nope\n"
     "iterations: {c: {}}\n", "not a defined emg_map"),
    # default_emg_map on a flat file is meaningless, not silently dropped
    ("emg_map: {E: [a]}\ndefault_emg_map: nonsense\niterations: {c: {}}\n",
     "single flat block"),
])
def test_bad_configs_fail_at_load(tmp_path, body, needle):
    with pytest.raises(ValueError, match=needle):
        S.load_session_yaml(write(tmp_path, body))


def test_an_undeclared_iteration_folder_says_so(tmp_path):
    write(tmp_path, NAMED)
    with pytest.raises(ValueError, match="not declared in session.yaml"):
        S.Iteration(str(tmp_path), "gpk_v2").trial_config("Squat_BW_01")


# --- the lenient path never raises -----------------------------------------
@pytest.mark.parametrize("cfg,expected", [
    ({"emg_map": {"n": {"E": ["c"]}, "E1": ["a"]}}, {"E": ["c"]}),        # mixed
    ({"emg_map": {"n": {"E": ["c"]}, "w": {"E": ["d"]}},
      "iterations": [{"name": "x"}]}, {"E": ["c"]}),                      # list form
    ({"emg_map": {"E": ["a", "b"]}, "default_emg_map": "junk"},
     {"E": ["a", "b"]}),                                                  # flat
    ({"emg_map": "not a dict"}, {}),
    ({}, {}),
])
def test_resolve_emg_map_non_strict_falls_back(cfg, expected):
    assert S.resolve_emg_map(cfg, "x", strict=False) == expected


def test_spec_emg_map_for(tmp_path):
    spec = S.read_session_yaml(write(tmp_path, NAMED))
    assert spec.emg_map_for("gpk_wide")["EMG09_l"][-1] == "perlong_l"
    assert spec.emg_map_for() == spec.emg_muscle_mapping   # session default
    with pytest.raises(ValueError, match="does not select one"):
        spec.emg_map_for("nope")


def test_xml_keeps_the_per_model_selector(tmp_path):
    spec = S.read_session_yaml(write(tmp_path, NAMED))
    xml = str(tmp_path / "session.xml")
    S.write_session_xml(spec, xml)
    assert [m.emg_map for m in S.read_session_xml(xml).models] == [
        "narrow", "triceps", "wide"]
