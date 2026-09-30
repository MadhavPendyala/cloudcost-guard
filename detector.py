"""Anomaly detection: rolling z-score (statistical) and Isolation Forest (ML)."""
import numpy as np
from sklearn.ensemble import IsolationForest


def zscore(vals, window=14, threshold=3.0):
    out = []
    for i in range(window, len(vals)):
        s = np.array(vals[i - window:i])
        m = s.mean()
        z = (vals[i] - m) / max(s.std(), m * 0.01)
        if abs(z) >= threshold:
            out.append({"i": i, "value": float(vals[i]), "expected": float(m), "score": float(z)})
    return out


def iforest(vals, contamination=0.04):
    v = np.array(vals, float)
    n = len(v)
    if n < 20:
        return []
    delta = np.r_[0, np.diff(v)]
    roll = np.array([v[max(0, i - 7):i].mean() if i else v[0] for i in range(n)])
    X = np.c_[v, delta, v - roll]  # value, day-over-day change, deviation from 7-day mean
    model = IsolationForest(n_estimators=150, random_state=42,
                            contamination=min(max(contamination, 0.005), 0.2)).fit(X)
    pred, score = model.predict(X), -model.score_samples(X)
    return [{"i": i, "value": float(v[i]), "expected": float(roll[i]), "score": float(score[i])}
            for i in range(n) if pred[i] == -1]
