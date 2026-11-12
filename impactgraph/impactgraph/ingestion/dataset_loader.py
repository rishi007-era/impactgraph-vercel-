"""UNSW-NB15 loading, cleaning and leakage-safe splitting.

Source: UNSW_NB15_training-set.csv (the official training partition, 175,341 records). The official
testing partition was not available offline, so this project re-splits the training partition internally:
stratified 60/20/20 train/validation/test by attack category, AFTER removing duplicate feature rows.
Reference: Moustafa & Slay (2015). Lab-generated 2015 traffic; NOT Colonial Pipeline traffic.

Leakage controls: id dropped; label and attack_cat never used as features; encoders/medians fit on the
training split only; exact duplicate feature rows removed before splitting (conflicting-label duplicates dropped).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

DEFAULT_PATH = os.path.join("data", "raw", "unsw-nb15", "UNSW_NB15_training-set.csv")
CATEGORICAL = ["proto", "service", "state"]
TARGET = "attack_cat"


@dataclass
class PreparedData:
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_val: pd.Series
    y_test: pd.Series
    features: list
    class_counts_raw: dict
    n_raw: int
    n_after_dedup: int
    n_conflicts_dropped: int


def load_raw(path: str = DEFAULT_PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"UNSW-NB15 file not found at {path}. See scripts/download_unsw.py")
    return pd.read_csv(path, encoding="utf-8-sig")


def prepare(path: str = DEFAULT_PATH, seed: int = 42) -> PreparedData:
    df = load_raw(path)
    n_raw = len(df)
    raw_counts = df[TARGET].value_counts().to_dict()
    df = df.replace([np.inf, -np.inf], np.nan)
    feat_cols = [c for c in df.columns if c not in ("id", "label", TARGET)]
    # remove rows with identical features but conflicting classes, then exact duplicates
    grp = df.groupby(feat_cols, dropna=False)[TARGET].transform("nunique")
    conflicts = int((grp > 1).sum())
    df = df[grp == 1].drop_duplicates(subset=feat_cols)
    n_dedup = len(df)
    tr, tmp = train_test_split(df, test_size=0.4, stratify=df[TARGET], random_state=seed)
    va, te = train_test_split(tmp, test_size=0.5, stratify=tmp[TARGET], random_state=seed)
    # categorical encoders fit on TRAIN only (unknown -> -1)
    maps = {c: {v: i for i, v in enumerate(sorted(tr[c].astype(str).unique()))} for c in CATEGORICAL}
    med = tr[[c for c in feat_cols if c not in CATEGORICAL]].median()

    def enc(d):
        d = d[feat_cols].copy()
        for c in CATEGORICAL:
            d[c] = d[c].astype(str).map(maps[c]).fillna(-1).astype(int)
        num = [c for c in feat_cols if c not in CATEGORICAL]
        d[num] = d[num].fillna(med)
        return d

    return PreparedData(enc(tr), enc(va), enc(te), tr[TARGET], va[TARGET], te[TARGET], feat_cols, raw_counts,
                        n_raw, n_dedup, conflicts)
