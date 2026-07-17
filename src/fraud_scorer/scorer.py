
# most real people don't sustain sub-60ms average
# gaps between keystrokes for an entire field.
FAST_TYPING_THRESHOLD_MS = 60

# Below this stddev (ms), typing is suspiciously uniform -- real humans are
# never this metronomic; scripted keystroke injection often is. Only
# applied together with FAST_TYPING_THRESHOLD_MS above, since a genuinely
# slow-but-steady typist alone isn't suspicious.
UNIFORM_TYPING_THRESHOLD_MS = 15


def score_session(session: dict) -> dict:
    """Returns {"is_bot": bool, "reasons": [...]}. Deliberately not a 0-1
    risk score with a tunable threshold -- either the paste/scripted-typing
    signal fired or it didn't, nothing in between to calibrate."""
    reasons = []

    if session.get("paste_detected"):
        reasons.append("Form field(s) were filled via paste rather than typed.")

    mean = session.get("typing_cadence_mean_ms") or 0
    std = session.get("typing_cadence_std_ms") or 0
    if mean > 0 and mean < FAST_TYPING_THRESHOLD_MS and std < UNIFORM_TYPING_THRESHOLD_MS:
        reasons.append(
            f"Typing was suspiciously fast and uniform (mean={mean:.0f}ms, std={std:.0f}ms)."
        )

    return {"is_bot": len(reasons) > 0, "reasons": reasons}
