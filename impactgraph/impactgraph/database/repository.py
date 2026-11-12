"""SQLite persistence (Phase 1). Stores configurations, scenarios, telemetry, anomaly results, attack paths,
propagation results, risk scores, isolation recommendations and experiment metrics, so any run can be reloaded.
Uses the standard library sqlite3 plus pandas; schema is portable to PostgreSQL in Phase 2.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS infrastructure_configs (config_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, json TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS nodes (config_id INTEGER, node_id TEXT, name TEXT, zone TEXT, node_type TEXT, importance REAL, json TEXT);
CREATE TABLE IF NOT EXISTS edges (config_id INTEGER, edge_id TEXT, source TEXT, target TEXT, edge_type TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS scenarios (scenario_id TEXT PRIMARY KEY, name TEXT, mode TEXT, description TEXT, assumptions TEXT);
CREATE TABLE IF NOT EXISTS runs (run_id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id TEXT, config_id INTEGER, seed INTEGER,
    trials INTEGER, created TEXT, runtime_s REAL, params_json TEXT);
CREATE TABLE IF NOT EXISTS attack_paths (run_id INTEGER, rank INTEGER, target TEXT, probability REAL, path_json TEXT);
CREATE TABLE IF NOT EXISTS propagation_results (run_id INTEGER, component_id TEXT, p_compromised REAL, p_failed REAL,
    p_degraded REAL, p_affected REAL, ci_low REAL, ci_high REAL, mean_time REAL);
CREATE TABLE IF NOT EXISTS replay_trace (run_id INTEGER, variant TEXT, component_id TEXT, t_compromised REAL, t_failed REAL, fail_kind TEXT, condition TEXT);
CREATE TABLE IF NOT EXISTS replay_edges (run_id INTEGER, variant TEXT, edge_id TEXT, t_start REAL, t_end REAL);
CREATE TABLE IF NOT EXISTS risk_scores (run_id INTEGER, json TEXT);
CREATE TABLE IF NOT EXISTS isolation_recommendations (run_id INTEGER, strategy TEXT, step INTEGER, edge_id TEXT, delta_j REAL,
    delta_impact REAL, delta_phys REAL, explanation TEXT);
CREATE TABLE IF NOT EXISTS strategy_results (run_id INTEGER, strategy TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS experiment_metrics (run_id INTEGER, category TEXT, metric TEXT, value REAL, detail TEXT);
CREATE TABLE IF NOT EXISTS anomaly_scores (run_id INTEGER, step INTEGER, component_id TEXT, anomaly_score REAL, alert INTEGER);
CREATE TABLE IF NOT EXISTS anomaly_results (run_id INTEGER, component_id TEXT, max_score REAL, first_alert_step INTEGER, explanation TEXT);
CREATE TABLE IF NOT EXISTS json_blobs (run_id INTEGER, name TEXT, json TEXT);
"""


class Repository:
    def __init__(self, path: str):
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    # ---- infrastructure ------------------------------------------------
    def save_infrastructure(self, ig) -> int:
        cur = self.con.execute("INSERT INTO infrastructure_configs(name,json,created) VALUES (?,?,?)",
                               (ig.name, ig.to_json(indent=0), datetime.now(timezone.utc).isoformat()))
        cid = cur.lastrowid
        for n in ig.nodes:
            self.con.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?)",
                             (cid, n.id, n.name, n.zone.value, n.node_type.value, n.operational_importance, json.dumps(n.to_dict())))
        for e in ig.edges:
            self.con.execute("INSERT INTO edges VALUES (?,?,?,?,?,?)",
                             (cid, e.id, e.source, e.target, e.edge_type.value, json.dumps(e.to_dict())))
        self.con.commit()
        return cid

    def load_infrastructure(self, config_id: int):
        from ..infrastructure.graph_builder import InfrastructureGraph
        row = self.con.execute("SELECT json FROM infrastructure_configs WHERE config_id=?", (config_id,)).fetchone()
        return InfrastructureGraph.from_json(row[0])

    def save_scenario(self, sc):
        self.con.execute("INSERT OR REPLACE INTO scenarios VALUES (?,?,?,?,?)",
                         (sc.id, sc.name, sc.mode, sc.description, json.dumps(list(sc.assumptions))))
        self.con.commit()

    # ---- runs -----------------------------------------------------------
    def new_run(self, scenario_id, config_id, seed, trials, params: dict) -> int:
        cur = self.con.execute("INSERT INTO runs(scenario_id,config_id,seed,trials,created,runtime_s,params_json) VALUES (?,?,?,?,?,?,?)",
                               (scenario_id, config_id, seed, trials, datetime.now(timezone.utc).isoformat(), 0.0, json.dumps(params)))
        self.con.commit()
        return cur.lastrowid

    def finish_run(self, run_id, runtime_s):
        self.con.execute("UPDATE runs SET runtime_s=? WHERE run_id=?", (runtime_s, run_id))
        self.con.commit()

    def save_df(self, table: str, df: pd.DataFrame, run_id: int):
        d = df.copy()
        d.insert(0, "run_id", run_id)
        d.to_sql(table, self.con, if_exists="append", index=False)

    def save_blob(self, run_id, name, obj):
        self.con.execute("INSERT INTO json_blobs VALUES (?,?,?)", (run_id, name, json.dumps(obj, default=float)))
        self.con.commit()

    def load_blob(self, run_id, name):
        row = self.con.execute("SELECT json FROM json_blobs WHERE run_id=? AND name=? ORDER BY rowid DESC LIMIT 1",
                               (run_id, name)).fetchone()
        return json.loads(row[0]) if row else None

    def execute(self, sql, params=()):
        self.con.execute(sql, params)
        self.con.commit()

    def df(self, sql, params=()) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.con, params=params)

    def list_runs(self) -> pd.DataFrame:
        return self.df("SELECT run_id, scenario_id, seed, trials, created, runtime_s FROM runs ORDER BY run_id DESC")

    def load_run(self, run_id: int) -> dict:
        q = lambda t: self.df(f"SELECT * FROM {t} WHERE run_id=?", (run_id,)).drop(columns=["run_id"], errors="ignore")
        run = self.df("SELECT * FROM runs WHERE run_id=?", (run_id,)).iloc[0].to_dict()
        risk = self.con.execute("SELECT json FROM risk_scores WHERE run_id=?", (run_id,)).fetchone()
        return {
            "run": run, "propagation": q("propagation_results"), "replay_nodes": q("replay_trace"),
            "replay_edges": q("replay_edges"), "attack_paths": q("attack_paths"),
            "risk": pd.DataFrame(json.loads(risk[0])) if risk else pd.DataFrame(),
            "recommendations": q("isolation_recommendations"),
            "strategies": pd.DataFrame([json.loads(r[1]) | {"strategy": r[0]} for r in
                                        self.con.execute("SELECT strategy,json FROM strategy_results WHERE run_id=?", (run_id,))]),
            "metrics": q("experiment_metrics"), "anomaly_scores": q("anomaly_scores"), "anomaly_results": q("anomaly_results"),
            "telemetry": self.df("SELECT * FROM telemetry WHERE run_id=?", (run_id,)).drop(columns=["run_id"], errors="ignore")
            if self._has("telemetry") else pd.DataFrame(),
        }

    def _has(self, table):
        return self.con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone() is not None
