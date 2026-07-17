import re
import sys
from datetime import date, datetime

import cv2
import pytesseract
from deepface import DeepFace

FACE_MATCH_THRESHOLD = 0.70   # DeepFace similarity below this = not a match
LIVENESS_REVIEW_THRESHOLD = 0.4  # below this = flag for review (see note below)


# OCR extract + validate 
def extract_and_validate_id(image_path: str) -> dict:
    """Read an ID card image, pull out Name/DOB/ID No/Nationality/Expiry,
    and check they're well-formed. Assumes a "Label: value" layout -- change
    the regexes below if your ID template looks different."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = gray.shape
    if h < 1000:
        scale = 1000 / h
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)

    raw_text = pytesseract.image_to_string(gray)

    name = _match(r"Name:\s*(.+)", raw_text)

    # DOB and Expiry are the only two YYYY-MM-DD-shaped values on the card
    dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", raw_text)
    dob = dates[0] if len(dates) >= 1 else None
    expiry = dates[-1] if len(dates) >= 2 else None

    # ID numbers are "ID" + 9 digits 
    id_match = re.search(r"\bID\d{9}\b", raw_text)
    id_number = id_match.group(0) if id_match else None
    if id_number is None:
        fallback = re.search(r"\b\d{9,11}\b", raw_text)
        id_number = fallback.group(0) if fallback else None

    # Nationality values are constrained to "Country A" / "Country B" 
    nat_match = re.search(r"\bCountry [AB]\b", raw_text)
    nationality = nat_match.group(0) if nat_match else None

    fields = {
        "name": name,
        "dob": dob,
        "id_number": id_number,
        "nationality": nationality,
        "expiry": expiry,
    }

    errors = []
    for key, value in fields.items():
        if value is None:
            errors.append(f"Missing or unreadable field: {key}")

    dob = _parse_date(fields["dob"])
    if fields["dob"] and dob is None:
        errors.append("DOB could not be parsed")
    elif dob:
        age = (date.today() - dob).days / 365.25
        if not (0 < age < 120):
            errors.append("DOB implies an implausible age")

    expiry = _parse_date(fields["expiry"])
    if expiry and expiry < date.today():
        errors.append("Document has expired")

    return {"fields": fields, "raw_text": raw_text, "is_valid": len(errors) == 0, "errors": errors}


def _match(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


# face match + liveness proxy
def face_match_and_liveness(id_image_path: str, selfie_image_path: str) -> dict:
    """Compare the ID photo to the selfie, plus a heuristic liveness score.

    IMPORTANT: liveness_score is NOT real liveness detection. True liveness
    needs a live signal (blink/motion from video, or depth). With static
    images all we can do is proxy signals a printed-photo or screen-replay
    attack would typically get wrong: face-detector confidence, sharpness,
    and face crop resolution. Say so explicitly in the demo -- this is a
    stand-in for the real thing, which is the "bonus extension" (live
    camera capture) territory.
    """
    result = DeepFace.verify(
        img1_path=id_image_path,
        img2_path=selfie_image_path,
        model_name="Facenet",
        detector_backend="opencv",
        enforce_detection=False,
    )
    distance, threshold = result["distance"], result["threshold"]
    similarity = max(0.0, 1.0 - (distance / (threshold * 2)))
    is_match = bool(result["verified"]) and similarity >= FACE_MATCH_THRESHOLD

    liveness_score, liveness_signals = _estimate_liveness(selfie_image_path)

    return {
        "face_match": {"is_match": is_match, "similarity_score": round(similarity, 4)},
        "liveness": {
            "liveness_score": liveness_score,
            "is_heuristic_proxy": True,  # always surface this in the demo/UI
            "signals": liveness_signals,
        },
    }


def _estimate_liveness(selfie_path: str) -> tuple[float, dict]:
    img = cv2.imread(selfie_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return 0.0, {"face_detected": False}

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    crop = gray[y:y + h, x:x + w]

    sharpness = min(1.0, cv2.Laplacian(crop, cv2.CV_64F).var() / 300.0)
    resolution = min(1.0, max(0.0, (min(w, h) - 80) / 120.0))
    score = round(0.5 * sharpness + 0.3 * resolution + 0.2 * 1.0, 4)

    return score, {"sharpness_score": round(sharpness, 4), "resolution_score": round(resolution, 4)}


# Run the whole pipeline: OCR + face match + liveness proxy, and return a
# decision (approved/rejected/review) with reasons.
def run_pipeline(id_image_path: str, selfie_image_path: str) -> dict:
    ocr = extract_and_validate_id(id_image_path)
    face = face_match_and_liveness(id_image_path, selfie_image_path)

    reasons = list(ocr["errors"])
    if not face["face_match"]["is_match"]:
        reasons.append(f"Face match failed (similarity={face['face_match']['similarity_score']})")
    if face["liveness"]["liveness_score"] < LIVENESS_REVIEW_THRESHOLD:
        reasons.append(f"Low liveness proxy score ({face['liveness']['liveness_score']})")

    if not ocr["is_valid"] or not face["face_match"]["is_match"]:
        status = "rejected"
    elif face["liveness"]["liveness_score"] < LIVENESS_REVIEW_THRESHOLD:
        status = "review"
    else:
        status = "approved"

    return {"ocr": ocr, "face": face, "decision": {"status": status, "reasons": reasons}}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python src/ekyc_pipeline/pipeline.py <id_image_path> <selfie_image_path>")
        sys.exit(1)

    result = run_pipeline(sys.argv[1], sys.argv[2])

    print("--- OCR fields ---")
    for k, v in result["ocr"]["fields"].items():
        print(f"  {k}: {v}")
    print(f"  valid: {result['ocr']['is_valid']}  errors: {result['ocr']['errors']}")

    print("--- Face match ---")
    print(f"  {result['face']['face_match']}")

    print("--- Liveness (heuristic proxy, not real liveness detection) ---")
    print(f"  {result['face']['liveness']}")

    print(f"--- Decision: {result['decision']['status']} ---")
    if result["decision"]["reasons"]:
        print(f"  reasons: {result['decision']['reasons']}")