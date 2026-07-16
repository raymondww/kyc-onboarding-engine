import json
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest

SEED = 42

FEATURE_NAMES = [
    "typing_cadence_mean_ms",
    "typing_cadence_std_ms",
    "session_duration_sec",
    "mouse_move_count",
]

RISK_THRESHOLD = 0.9


def sessions_to_matrix(sessions: list[dict]) -> np.ndarray:
    return np.array([[s[f] for f in FEATURE_NAMES] for s in sessions])


def train_fraud_model(human_sessions: list[dict]) -> tuple[IsolationForest, float, float]:
    """Trains on sessions you believe are legitimate (e.g. historical
    successful onboardings). Returns the model plus the min/max "normalcy"
    score seen during training, used to calibrate score_session()'s 0-1
    output against this specific training distribution instead of a
    hardcoded magic constant."""
    X = sessions_to_matrix(human_sessions)
    model = IsolationForest(contamination=0.05, random_state=SEED)
    model.fit(X)

    # score_samples: higher = more "normal"/inlier-like, lower = more anomalous.
    train_scores = model.score_samples(X)
    return model, float(train_scores.min()), float(train_scores.max())


def score_session(model: IsolationForest, score_min: float, score_max: float, session: dict) -> float:
    """Returns a 0-1 risk score for one session -- higher = more suspicious.
    Normalized against the training distribution's own score range (from
    train_fraud_model), then inverted (normal/inlier -> low risk) and
    clipped, since a genuinely novel session can score outside the training
    range entirely."""
    X = sessions_to_matrix([session])
    raw_score = model.score_samples(X)[0]

    normalcy = (raw_score - score_min) / (score_max - score_min + 1e-9)
    risk_score = 1.0 - np.clip(normalcy, 0.0, 1.0)
    return round(float(risk_score), 4)


if __name__ == "__main__":
    # Quick manual test: train on the synthetic "human" sessions only, then
    # score EVERY session (human and bot) and check how well the risk score
    # actually separates them against the ground-truth is_bot label.
    ROOT = Path(__file__).resolve().parents[2]
    sessions = json.loads((ROOT / "data" / "synthetic" / "sessions.json").read_text())

    human_sessions = [s for s in sessions if not s["is_bot"]]
    model, score_min, score_max = train_fraud_model(human_sessions)

    correct = 0
    for s in sessions:
        risk = score_session(model, score_min, score_max, s)
        predicted_bot = risk > RISK_THRESHOLD
        correct += predicted_bot == s["is_bot"]
        flag = "BOT " if s["is_bot"] else "human"
        hit = "correct" if predicted_bot == s["is_bot"] else "WRONG"
        print(f"{s['session_id']:22} true={flag} risk={risk:.4f} predicted_bot={predicted_bot} [{hit}]")

    print(f"\nAccuracy: {correct}/{len(sessions)} ({100 * correct / len(sessions):.1f}%)")
