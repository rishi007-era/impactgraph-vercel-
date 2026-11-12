"""Integration: one complete scenario through every module, persisted and reloaded."""
import pandas as pd
import pytest

from impactgraph.database.repository import Repository
from impactgraph.detection.isolation_forest import NodeAnomalyDetector
from impactgraph.experiments import runner
from impactgraph.infrastructure.topology import build_phase1_topology
from impactgraph.ingestion.telemetry_generator import generate_episode
from impactgraph.simulation.propagation import PropagationModel


def test_full_scenario_runs_persists_and_reloads(tmp_path):
    ig = build_phase1_topology()
    model = PropagationModel(ig)
    tr = pd.concat([generate_episode(ig, 100 + i, episode_id=f"t{i}") for i in range(3)], ignore_index=True)
    va = pd.concat([generate_episode(ig, 200 + i, episode_id=f"v{i}") for i in range(2)], ignore_index=True)
    det = NodeAnomalyDetector(ig, use_residual=False, n_estimators=40).fit(tr, va)
    art = runner.Artifacts(det, det, runner.DummyBridge(), {}, {})
    repo = Repository(str(tmp_path / "t.db"))
    cid = repo.save_infrastructure(ig)
    rid = runner.run_scenario(ig, model, art, repo, cid, "S3", seed=1, trials=60, log=lambda *_: None)
    d = repo.load_run(rid)
    assert len(d["propagation"]) == 24 and len(d["risk"]) == 24
    assert set(d["strategies"].strategy) == {"no_isolation", "initial_component", "full_shutdown", "impactgraph_greedy"}
    assert len(d["telemetry"]) == 24 * 240 and len(d["anomaly_scores"]) == 24 * 240
    assert set(d["replay_nodes"].variant) == {"before", "after"} and len(d["metrics"]) > 20
    # the stored infrastructure reloads and is identical in size
    assert len(repo.load_infrastructure(cid).nodes) == 24
    # reproducibility: same seed -> same stored results
    rid2 = runner.run_scenario(ig, model, art, repo, cid, "S3", seed=1, trials=60, log=lambda *_: None)
    a, b = repo.load_run(rid)["propagation"], repo.load_run(rid2)["propagation"]
    pd.testing.assert_frame_equal(a, b)
    repo.close()
