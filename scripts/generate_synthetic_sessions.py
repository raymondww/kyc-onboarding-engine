import json
from pathlib import Path

import numpy as np

SEED = 42
NUM_HUMAN = 80  
NUM_BOT = 20

ROOT = Path(__file__).resolve().parent.parent
SESSIONS_OUT = ROOT / "data" / "synthetic" / "sessions.json"

FEATURE_NAMES = [
    "typing_cadence_mean_ms",
    "typing_cadence_std_ms",
    "session_duration_sec",
    "mouse_move_count",
]


def generate_human_session(rng: np.random.Generator) -> dict:
    return {
        # Natural typing: ~180ms between keystrokes on average, with real
        # variability (pauses to think, corrections, etc.)
        "typing_cadence_mean_ms": max(50, rng.normal(180, 40)),
        "typing_cadence_std_ms": max(5, rng.normal(60, 15)),
        "session_duration_sec": max(1.5, rng.normal(9, 4)),
        # Modest natural mouse movement clicking between 3 fields 
        "mouse_move_count": max(0, int(rng.poisson(10))),
    }


def generate_bot_session(rng: np.random.Generator) -> dict:
    return {
        # Scripted form-fill: very fast, very little gap between "keystrokes".
        "typing_cadence_mean_ms": max(1, rng.normal(25, 10)),
        # Suspiciously uniform timing -- low variance is itself a signal.
        "typing_cadence_std_ms": max(0.5, rng.normal(3, 2)),
        # Whole (short) form filled near-instantly.
        "session_duration_sec": max(0.2, rng.normal(1, 0.5)),
        # Little to no real mouse movement -- fields set programmatically.
        "mouse_move_count": max(0, int(rng.poisson(1))),
    }


def main():
    SESSIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    sessions = []
    for i in range(NUM_HUMAN):
        session = generate_human_session(rng)
        session["session_id"] = f"session_human_{i:03d}"
        session["is_bot"] = False
        sessions.append(session)

    for i in range(NUM_BOT):
        session = generate_bot_session(rng)
        session["session_id"] = f"session_bot_{i:03d}"
        session["is_bot"] = True
        sessions.append(session)

    # Round for readability
    for s in sessions:
        for key in FEATURE_NAMES:
            s[key] = round(s[key], 2)

    SESSIONS_OUT.write_text(json.dumps(sessions, indent=2))
    print(f"Generated {NUM_HUMAN} human-like + {NUM_BOT} bot-like sessions -> {SESSIONS_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
