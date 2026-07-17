import sys
from datetime import date, datetime
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parents[2]  # router.py -> onboarding_engine -> src -> repo root

sys.path.insert(0, str(ROOT))                            # for `src.regulatory_engine...`, `src.ekyc_pipeline...`
sys.path.insert(0, str(ROOT / "src" / "osint_agent"))     # for run_agent's own flat imports

from src.ekyc_pipeline.pipeline import LIVENESS_REVIEW_THRESHOLD, extract_and_validate_id, face_match_and_liveness  # noqa: E402
from src.regulatory_engine.cdd_validator import get_cdd_config    # noqa: E402
import run_agent  # noqa: E402

NAME_MATCH_THRESHOLD = 80


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _verify_form_matches_id(full_name: str, dob: str, ocr_fields: dict) -> list[str]:
    """Returns a list of mismatch reasons (empty if everything lines up).
    Only checks fields OCR actually managed to read -- if OCR couldn't read
    a field at all, that's already caught separately as a "Missing or
    unreadable field" error from extract_and_validate_id()."""
    reasons = []

    id_name = ocr_fields.get("name")
    if id_name:
        name_score = fuzz.token_sort_ratio(full_name.lower(), id_name.lower())
        if name_score < NAME_MATCH_THRESHOLD:
            reasons.append(
                f"Form name does not match ID name (similarity={name_score:.0f}/100, ID reads '{id_name}')"
            )

    id_dob = _parse_date(ocr_fields.get("dob"))
    form_dob = _parse_date(dob)
    if id_dob and form_dob and id_dob != form_dob:
        reasons.append(f"Form date of birth ({form_dob}) does not match ID date of birth ({id_dob})")

    return reasons


def _step(step_id: str, message: str) -> dict:
    """One progress update -- printed to the terminal immediately (so you
    see it live in the uvicorn console) and also returned as an event dict
    so callers can stream the same message to a frontend. Kept to one place
    so the terminal and the UI never say different things."""
    print(f"[onboarding] {message}")
    return {"event": "step", "step": step_id, "message": message}


def run_onboarding_steps(
    full_name: str,
    dob: str,
    country: str,
    id_image_path: str,
    selfie_image_path: str | None = None,
):
    """Generator version of run_onboarding(): yields one {"event": "step",
    ...} dict per stage as it actually happens, then a final {"event":
    "result", ...} dict with the same shape run_onboarding() returns.
    run_onboarding() below just drains this generator and returns the last
    event -- so the CLI script, the streaming FastAPI endpoint, and any
    other caller all go through identical logic, no duplicated business
    rules between a "quiet" and a "verbose" code path.
    """
    cdd_config = get_cdd_config(country)
    verification_method = cdd_config["verification_method"]

    if verification_method == "Video KYC":
        if not selfie_image_path:
            yield _step("document_check", "Selfie image required for Video KYC verification.")
            yield {
                "event": "result", "applicant": full_name, "status": "rejected",
                "stage": "document_check", "reasons": ["Selfie image required for Video KYC verification."],
            }
            return

        yield _step("document_check", "Extracting information from ID...")
        ocr = extract_and_validate_id(id_image_path)
        yield _step(
            "document_check_done",
            "ID extraction complete." if ocr["is_valid"] else f"ID extraction found issues: {ocr['errors']}",
        )

        yield _step("face_match", "Matching selfie photo to ID photo...")
        face = face_match_and_liveness(id_image_path, selfie_image_path)
        yield _step(
            "face_match_done",
            "Face match complete." if face["face_match"]["is_match"] else "Face match failed.",
        )
        face_match = face["face_match"]
        liveness = face["liveness"]

        # Same decision logic as ekyc_pipeline.run_pipeline() -- duplicated
        # here (rather than calling run_pipeline() as one opaque blocking
        # call) so OCR and face-match can each report as their own step.
        # Keep these two in sync if the decision rule ever changes.
        reasons = list(ocr["errors"])
        if not face_match["is_match"]:
            reasons.append(f"Face match failed (similarity={face_match['similarity_score']})")
        if liveness["liveness_score"] < LIVENESS_REVIEW_THRESHOLD:
            reasons.append(f"Low liveness proxy score ({liveness['liveness_score']})")

        if not ocr["is_valid"] or not face_match["is_match"]:
            doc_status = "rejected"
        elif liveness["liveness_score"] < LIVENESS_REVIEW_THRESHOLD:
            doc_status = "review"
        else:
            doc_status = "approved"
        doc_decision = {"status": doc_status, "reasons": reasons}

        yield _step("identity_check", "Verifying form details match ID...")
        mismatch_reasons = _verify_form_matches_id(full_name, dob, ocr["fields"])
        yield _step(
            "identity_check_done",
            "Identity match confirmed." if not mismatch_reasons else f"Identity mismatch: {mismatch_reasons}",
        )
        if mismatch_reasons:
            doc_decision = {"status": "rejected", "reasons": [*doc_decision["reasons"], *mismatch_reasons]}

    elif verification_method == "eKYC":
        # ID-only check for now -- see module docstring. No face_match/
        # liveness produced on this branch since no selfie is collected.
        yield _step("document_check", "Extracting information from ID...")
        ocr = extract_and_validate_id(id_image_path)
        yield _step(
            "document_check_done",
            "ID extraction complete." if ocr["is_valid"] else f"ID extraction found issues: {ocr['errors']}",
        )

        yield _step("identity_check", "Verifying form details match ID...")
        mismatch_reasons = _verify_form_matches_id(full_name, dob, ocr["fields"])
        yield _step(
            "identity_check_done",
            "Identity match confirmed." if not mismatch_reasons else f"Identity mismatch: {mismatch_reasons}",
        )
        doc_decision = {
            "status": "approved" if (ocr["is_valid"] and not mismatch_reasons) else "rejected",
            "reasons": [*ocr["errors"], *mismatch_reasons],
        }
        face_match = None
        liveness = None

    else:
        yield {
            "event": "result", "applicant": full_name, "status": "not_implemented",
            "reason": f"{country} requires {verification_method}, which isn't built yet.",
        }
        return

    if doc_decision["status"] == "rejected":
        yield {
            "event": "result", "applicant": full_name, "status": "rejected",
            "stage": "document_check", "reasons": doc_decision["reasons"],
        }
        return

    # Document check passed (or is a soft "review") -- hand off to OSINT for
    # sanctions + adverse media risk. Live DuckDuckGo search + local Ollama
    # LLM call, so this is slow (~seconds) and needs Ollama running locally.
    yield _step("osint_check", "Running background check (sanctions + adverse media)...")
    osint_result = run_agent.run_osint_agent(full_name, applicant_dob=dob)
    yield _step("osint_check_done", f"Background check complete ({osint_result['risk_flag']} risk).")

    final_status = "approved"
    if doc_decision["status"] == "review":
        final_status = "review"
    if osint_result["risk_flag"] == "MEDIUM":
        final_status = "review"
    if osint_result["risk_flag"] == "HIGH":
        final_status = "rejected"

    yield _step(
        "finalize",
        "Submitted successfully." if final_status == "approved" else f"Verification {final_status}.",
    )
    yield {
        "event": "result",
        "applicant": full_name,
        "status": final_status,
        "document_decision": doc_decision,
        "face_match": face_match,
        "liveness": liveness,
        "osint_risk_flag": osint_result["risk_flag"],
        "osint_risk_summary": osint_result["risk_summary"],
    }


def run_onboarding(
    full_name: str,
    dob: str,
    country: str,
    id_image_path: str,
    selfie_image_path: str | None = None,
) -> dict:
    """Routes one applicant through document verification then OSINT and
    returns the final result only (no intermediate step events) -- what
    scripts/run_onboarding_demo.py and any other non-streaming caller want.
    Steps still print to the terminal as they happen; this just doesn't
    also hand them back to the caller. See run_onboarding_steps() for the
    streaming version the live FastAPI endpoint uses."""
    result = None
    for event in run_onboarding_steps(full_name, dob, country, id_image_path, selfie_image_path):
        if event["event"] == "result":
            result = event
    result = dict(result)
    result.pop("event", None)
    return result
