"""Cached data access: the dashboard only displays results that were computed and stored by the backend."""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import streamlit as st

from ..database.repository import Repository
from ..simulation.scenarios import SCENARIOS
from . import theme as T

DB = os.environ.get("IMPACTGRAPH_DB", "impactgraph.db")
CONFIG = {"displayModeBar": False}


def stamp(db=DB) -> float:
    return os.path.getmtime(db) if os.path.exists(db) else 0.0


@st.cache_data(show_spinner=False)
def list_runs(db: str, s: float) -> pd.DataFrame:
    r = Repository(db)
    try:
        return r.list_runs()
    finally:
        r.close()


@st.cache_data(show_spinner=False)
def load_run(db: str, run_id: int, s: float) -> dict:
    r = Repository(db)
    try:
        return r.load_run(run_id)
    finally:
        r.close()


@st.cache_data(show_spinner=False)
def load_blob(db: str, run_id: int, name: str, s: float):
    r = Repository(db)
    try:
        return r.load_blob(run_id, name)
    finally:
        r.close()


@st.cache_resource(show_spinner=False)
def load_graph(db: str, config_id: int, s: float):
    r = Repository(db)
    try:
        return r.load_infrastructure(config_id)
    finally:
        r.close()


def strategy_row(d: dict, key: str) -> dict:
    df = d["strategies"]
    row = df[df.strategy == key]
    return row.iloc[0].to_dict() if len(row) else {}


def pct(x, nd=0) -> str:
    return f"{100 * x:.{nd}f}%"


def replay_state(rn: pd.DataFrame, step: float, final: bool) -> dict:
    fills = {}
    for r in rn.itertuples():
        cond = "normal"
        if not np.isnan(r.t_failed) and r.t_failed <= step:
            cond = "failed"
        elif not np.isnan(r.t_compromised) and r.t_compromised <= step:
            cond = "compromised"
        elif final and r.condition in ("degraded", "failed", "compromised"):
            cond = r.condition
        fills[r.component_id] = T.COND_COLOR[cond]
    return fills


def replay_max(rn: pd.DataFrame) -> float:
    vals = list(rn.t_compromised.dropna()) + list(rn.t_failed.dropna())
    return float(max(vals)) if vals else 0.0


def scenario_of(sid: str):
    return SCENARIOS[sid]
