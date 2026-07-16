from rapidfuzz import fuzz, process
import pandas as pd
import re

def load_sdn_list():
    """Load the real OFAC SDN list (individuals only), including DOB extracted from 'reason'."""
    sdn_df = pd.read_csv(
        "data/raw/sdn.csv",
        header=None,
        names=["uid", "name", "entity", "region", "role", "vessel_id",
               "vessel_type", "vessel_length", "vessel_width", "country", "null", "reason"]
    )
    sdn_df = sdn_df.loc[sdn_df["entity"] == "individual", ["name", "reason"]].reset_index(drop=True)
    sdn_df["dob"] = sdn_df["reason"].apply(extract_dob)
    return sdn_df


def extract_dob(reason_text):
    """Extract DOB from the SDN 'reason' field, if present. Returns a date or None."""
    if pd.isna(reason_text):
        return None
    match = re.search(r'DOB\s+([^;]+)', str(reason_text))
    if not match:
        return None
    dob_str = match.group(1).strip()
    dob = pd.to_datetime(dob_str, errors='coerce')
    return dob.date() if pd.notna(dob) else None


def check_ofac_match(applicant_profile, sdn_df, threshold=90):
    """
    Check applicant against local OFAC SDN list.
    Uses name similarity + DOB alignment (not region/country, which is unreliable in the SDN data).
    """
    name = applicant_profile["full_name"]
    applicant_dob = applicant_profile.get("dob")

    match_result = process.extractOne(
        name, sdn_df["name"], scorer=fuzz.token_sort_ratio
    )

    if match_result is None:
        return {"ofac_hit": False, "confidence": None, "score": 0}

    matched_name, best_score, matched_idx = match_result

    if best_score < threshold:
        return {"ofac_hit": False, "confidence": None, "score": best_score}

    matched_dob = sdn_df.loc[matched_idx, "dob"]

    # Compare DOBs if both are available
    dob_matches = None
    if applicant_dob and matched_dob:
        applicant_dob_parsed = pd.to_datetime(applicant_dob).date() if isinstance(applicant_dob, str) else applicant_dob
        dob_matches = (applicant_dob_parsed == matched_dob)

    if best_score >= 98 and dob_matches:
        confidence = "HIGH"       # exact name + exact DOB match, very strong signal
    elif best_score >= 98 and dob_matches is None:
        confidence = "MEDIUM"     # exact name match, but no DOB to confirm (needs manual review)
    elif best_score >= 98 and dob_matches is False:
        confidence = "MEDIUM"     # exact name match, but DOB conflicts - likely a different person, still worth reviewing
    else:
        confidence = "MEDIUM"     # fuzzy name match only

    return {
        "ofac_hit": True,
        "confidence": confidence,
        "score": best_score,
        "matched_name": matched_name,
        "matched_dob": matched_dob,
        "dob_matches": dob_matches
    }


if __name__ == "__main__":
    import re

    sdn_df = load_sdn_list()

    with open("data/synthetic/synthetic_profiles.json", "r") as f:
        profiles_df = pd.read_json(f)

    for profile in profiles_df.to_dict(orient="records"):
        result = check_ofac_match(profile, sdn_df)
        if result["ofac_hit"]:
            print(f"{profile['full_name']:40} | HIT  | Confidence: {result['confidence']:6} | Score: {result['score']:.1f} | DOB match: {result['dob_matches']}")
        else:
            print(f"{profile['full_name']:40} | none | Score: {result['score']:.1f}")
        print(result)