import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "synthetic" / "manifest.json"

sys.path.insert(0, str(ROOT))  # for `src.onboarding_engine...`

from src.onboarding_engine.router import run_onboarding  # noqa: E402


if __name__ == "__main__":
    if not MANIFEST_PATH.exists():
        print(f"Missing {MANIFEST_PATH}. Run scripts/generate_synthetic_kyc_data.py first.")
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text())

    for applicant in manifest:
        print(f"\n=== {applicant['full_name']} ({applicant['case_type']}) ===")
        result = run_onboarding(
            full_name=applicant["full_name"],
            dob=applicant["dob"],
            country=applicant["country"],
            id_image_path=str(ROOT / applicant["id_image"]),
            selfie_image_path=str(ROOT / applicant["selfie_image"]),
        )
        print(json.dumps(result, indent=2, default=str))