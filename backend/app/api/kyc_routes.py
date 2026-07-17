import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

ROOT = Path(__file__).resolve().parents[3]  # api -> app -> backend -> repo root
sys.path.insert(0, str(ROOT))

from src.onboarding_engine.router import run_onboarding_steps  # noqa: E402
from src.regulatory_engine.cdd_validator import get_cdd_config  # noqa: E402

router = APIRouter(prefix="/kyc", tags=["kyc"])

UPLOAD_DIR = ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Same backlog pattern as session_routes.py's BACKLOG_PATH -- JSONL so
# appends are cheap and a crash mid-write can't corrupt earlier entries.
BACKLOG_PATH = ROOT / "data" / "kyc_logs.jsonl"
_backlog_lock = Lock()

# The only rejection reason that's safe (and useful) to hand back to the
# client directly -- it's a "you forgot to attach a file" error, not a
# security-relevant signal about how the decision was made.
CLIENT_VISIBLE_REASONS = {"Selfie image required for Video KYC verification."}


def _save_upload(upload: UploadFile, dest_dir: Path, prefix: str) -> str:
    dest = dest_dir / f"{prefix}_{upload.filename}"
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return str(dest)


@router.post("/verify")
async def verify_kyc(
    id_image: UploadFile = File(...),
    selfie_image: UploadFile | None = File(None),
    full_name: str = Form(...),
    dob: date = Form(...),
    country: str = Form(...),
) -> StreamingResponse:
    try:
        get_cdd_config(country)  # fail fast with a clean 400 before opening the stream
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported country: {country}")

    # Each submission gets its own upload folder (name + timestamp) so
    # concurrent submissions never overwrite each other's files.
    session_dir = UPLOAD_DIR / f"{full_name.replace(' ', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
    session_dir.mkdir(parents=True, exist_ok=True)

    id_image_path = _save_upload(id_image, session_dir, "id")
    selfie_image_path = _save_upload(selfie_image, session_dir, "selfie") if selfie_image is not None else None

    def event_stream():
        result = None
        for event in run_onboarding_steps(
            full_name=full_name,
            dob=dob.isoformat(),
            country=country,
            id_image_path=id_image_path,
            selfie_image_path=selfie_image_path,
        ):
            if event["event"] == "result":
                result = event
            else:
                yield json.dumps(event) + "\n"

        log_entry = {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "full_name": full_name,
            "dob": dob.isoformat(),
            "country": country,
            "id_image_path": id_image_path,
            "selfie_image_path": selfie_image_path,
            **{k: v for k, v in result.items() if k != "event"},
        }
        with _backlog_lock:
            with BACKLOG_PATH.open("a") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")

        reason = None
        if result["status"] == "not_implemented":
            reason = result.get("reason")
        elif result["status"] == "rejected":
            visible = [r for r in result.get("reasons", []) if r in CLIENT_VISIBLE_REASONS]
            if visible:
                reason = visible[0]

        yield json.dumps({"event": "result", "status": result["status"], "reason": reason}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
