import numpy as np
import pandas as pd
import pytest

from impactgraph.detection.isolation_forest import NodeAnomalyDetector
from impactgraph.infrastructure.telemetry_spec import TELEMETRY_FEATURES
from impactgraph.infrastructure.topology import build_phase1_topology
from impactgraph.ingestion.telemetry_generator import FEATURES, generate_episode

IG = build_phase1_topology()


@pytest.fixture(scope="module")
def det():
    tr = pd.concat([generate_episode(IG, 100 + i, episode_id=f"t{i}") for i in range(4)], ignore_index=True)
    va = pd.concat([generate_episode(IG, 200 + i, episode_id=f"v{i}") for i in range(2)], ignore_index=True)
    return NodeAnomalyDetector(IG, use_residual=False, n_estimators=60).fit(tr, va)


def test_generator_is_reproducible_and_documented():
    a, b = generate_episode(IG, 1), generate_episode(IG, 1)
    pd.testing.assert_frame_equal(a, b)
    assert set(FEATURES) == set(TELEMETRY_FEATURES)                       # every feature has unit + range
    assert {"timestamp", "component_id", "zone", "label", "severity"} <= set(a.columns)
    assert (a.label == "normal").all()


def test_normal_values_stay_in_documented_ranges_mostly():
    a = generate_episode(IG, 2)
    for f in ("cpu_util_pct", "pressure_bar"):
        spec = TELEMETRY_FEATURES[f]
        x = a[f].dropna()
        assert ((x >= spec.normal_low * 0.7) & (x <= spec.normal_high * 1.3)).mean() > 0.95


def test_injected_failure_is_labelled_with_ground_truth():
    tr = {"compromised": {}, "failed": {"PH04": (0.0, "actuation")}, "services": {}}
    ep = generate_episode(IG, 3, trace=tr)
    assert (ep[(ep.component_id == "PH04") & (ep.step >= 60)].label == "physical_failure").all()
    assert (ep[(ep.component_id == "PH04") & (ep.step < 60)].label == "normal").all()
    assert (ep[(ep.component_id == "PH05")].label.isin(["normal", "downstream_effect"])).all()


def test_detector_flags_pump_failure_and_not_normal_operation(det):
    tr = {"compromised": {}, "failed": {"PH04": (0.0, "actuation")}, "services": {}}
    ep = generate_episode(IG, 301, trace=tr, episode_id="e")
    al = det.alerts(det.score(ep))
    first = al[(al.component_id == "PH04") & al.alert].step.min()
    assert 60 <= first <= 66                                              # alert within a few minutes of onset
    normal = generate_episode(IG, 302, episode_id="n")
    assert det.alerts(det.score(normal)).alert.mean() < 0.01              # low false-alarm rate


def test_scores_are_calibrated_and_explainable(det):
    tr = {"compromised": {"V02": 0.0}, "failed": {}, "services": {}}
    ep = generate_episode(IG, 303, trace=tr, episode_id="e")
    sc = det.score(ep)
    assert sc.anomaly_score.between(0, 1).all()
    ex = det.explain(ep, "V02", 65)
    assert ex and ex[0]["feature"] in ("auth_events_per_min", "conn_per_min") and abs(ex[0]["z"]) > 3
