from rapidfuzz import fuzz

def check_ofac_match(applicant_profile, sdn_df, threshold=90):
    """
    Check applicant against local OFAC SDN list.
    Returns match info including confidence level based on name + region alignment.
    """
    name = applicant_profile["full_name"]
    country = applicant_profile.get("country", "")

    best_match = None
    best_score = 0

    for _, row in sdn_df.iterrows():
        score = fuzz.token_sort_ratio(name.lower(), str(row["name"]).lower())
        if score > best_score:
            best_score = score
            best_match = row

    if best_score < threshold:
        return {"ofac_hit": False, "confidence": None, "score": best_score}

if __name__ == "__main__":
    import pandas as pd

    # Load SDN list
    with open("data/synthetic/synthetic_profiles.json", "r") as f:
        sdn_df = pd.read_json(f)
    for index,item in sdn_df.iterrows():
        name = item["full_name"]
        dob = item["dob"]
        country = item.get("country", "")
        print(f"Checking {name} ({dob}, {country}) against OFAC SDN list...")
