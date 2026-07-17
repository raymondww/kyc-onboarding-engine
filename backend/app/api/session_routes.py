import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

ROOT = Path(__file__).resolve().parents[3]  # api -> app -> backend -> repo root
sys.path.insert(0, str(ROOT))

from src.fraud_scorer.scorer import RISK_THRESHOLD, score_session, train_fraud_model  # noqa: E402

router = APIRouter(prefix="/session", tags=["fraud"])

SESSIONS_PATH = ROOT / "data" / "synthetic" / "sessions.json"
_sessions = json.loads(SESSIONS_PATH.read_text())
_human_sessions = [s for s in _sessions if not s["is_bot"]]
_model, _score_min, _score_max = train_fraud_model(_human_sessions)

# Every onboarding form submission (data + fraud score + verdict) gets
# appended here as one JSON line per submission -- this is the "backlog":
# nothing shown to the user, all logged server-side for you/the team to
# review later. JSONL (not one big JSON array) so appends are cheap and a
# crash mid-write can't corrupt earlier entries.
BACKLOG_PATH = ROOT / "data" / "session_logs.jsonl"
_backlog_lock = Lock()  # uvicorn can serve requests concurrently; avoid interleaved writes


class SessionFeatures(BaseModel):
    typing_cadence_mean_ms: float
    typing_cadence_std_ms: float
    session_duration_sec: float
    mouse_move_count: int = 0


class SessionScoreResponse(BaseModel):
    risk_score: float
    is_bot: bool
    threshold: float


@router.post("/score", response_model=SessionScoreResponse)
def score(features: SessionFeatures) -> SessionScoreResponse:
    """Pure scoring endpoint -- kept as-is for testing/debugging the model
    directly (this is what we curled earlier to verify it works). The real
    form flow below (`/submit`) is what the frontend actually calls now."""
    risk_score = score_session(_model, _score_min, _score_max, features.model_dump())
    return SessionScoreResponse(
        risk_score=risk_score,
        is_bot=risk_score > RISK_THRESHOLD,
        threshold=RISK_THRESHOLD,
    )


class OnboardingFormSubmission(BaseModel):
    full_name: str
    dob: date
    address: str
    # Must be exactly "Country A" or "Country B" -- matches the "country" key
    # in cdd_configs/cdd_configs.json, since this is what decides eKYC vs
    # ID-only verification in the next step of the flow.
    country: str
    typing_cadence_mean_ms: float
    typing_cadence_std_ms: float
    session_duration_sec: float
    mouse_move_count: int = 0

    # Defense in depth: the frontend already blocks today/future DOBs before
    # this request is ever sent, but never trust the client alone -- anyone
    # can call this endpoint directly (curl, a bot skipping the UI entirely)
    # bypassing whatever JS validation exists. Reject here too.
    @field_validator("dob")
    @classmethod
    def dob_must_be_in_the_past(cls, value: date) -> date:
        if value >= date.today():
            raise ValueError("Date of birth cannot be today or in the future")
        return value


class SubmissionResult(BaseModel):
    """Only a pass/fail status -- no risk_score, no threshold, no feature
    values. Enough for the frontend to gate progression to the next step,
    without exposing exactly how close a real bad actor came to slipping
    through, or which signals mattered. The full detail (including
    risk_score) only exists in the backlog file, server-side."""
    status: str  # "passed" | "flagged"


@router.post("/submit", response_model=SubmissionResult)
def submit_onboarding_form(submission: OnboardingFormSubmission) -> SubmissionResult:
    features = {
        "typing_cadence_mean_ms": submission.typing_cadence_mean_ms,
        "typing_cadence_std_ms": submission.typing_cadence_std_ms,
        "session_duration_sec": submission.session_duration_sec,
        "mouse_move_count": submission.mouse_move_count,
    }
    risk_score = score_session(_model, _score_min, _score_max, features)
    is_bot = risk_score > RISK_THRESHOLD

    log_entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "full_name": submission.full_name,
        "dob": submission.dob.isoformat(),
        "address": submission.address,
        "country": submission.country,
        **features,
        "risk_score": risk_score,
        "is_bot": is_bot,
        "threshold": RISK_THRESHOLD,
    }

    with _backlog_lock:
        with BACKLOG_PATH.open("a") as f:
            f.write(json.dumps(log_entry) + "\n")

    return SubmissionResult(status="flagged" if is_bot else "passed")