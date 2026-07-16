import os
import time
import requests
from rapidfuzz import fuzz
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

COURTLISTENER_API_URL = "https://www.courtlistener.com/api/rest/v4/search/"
COURTLISTENER_OPINION_URL = "https://www.courtlistener.com/api/rest/v4/opinions/{}/"
COURTLISTENER_TOKEN = os.environ.get("COURTLISTENER_API_TOKEN")  
FINANCIAL_RISK_KEYWORDS = [
    "fraud", "money laundering", "embezzlement", "securities",
    "ponzi", "wire fraud", "bank fraud", "racketeering", "rico",
    "sanctions", "bribery", "corruption", "tax evasion", "forgery"
]

def search_court_records(applicant_name, max_results=5):
    """
    Search CourtListener's case law database for records mentioning the applicant.

    Returns a list of dicts: [{"case_name": ..., "date_filed": ..., "url": ..., "snippet": ...}, ...]
    """
    if not COURTLISTENER_TOKEN:
        print("Warning: COURTLISTENER_API_TOKEN not set. Skipping court records check.")
        return []

    headers = {"Authorization": f"Token {COURTLISTENER_TOKEN}"}
    params = {
        "q": f'"{applicant_name}"',
        "type": "o",  # opinions (case law)
    }

    try:
        response = requests.get(COURTLISTENER_API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"CourtListener search failed for {applicant_name}: {e}")
        return []

    results = []
    for item in data.get("results", [])[:max_results]:
        opinions = item.get("opinions", [])
        opinion_id = opinions[0].get("id") if opinions else None

        results.append({
            "case_name": item.get("caseName", ""),
            "date_filed": item.get("dateFiled", ""),
            "court": item.get("court", ""),
            "url": f"https://www.courtlistener.com{item.get('absolute_url', '')}",
            "opinion_id": opinion_id,
        })
    return results

def fetch_opinion_text(opinion_id, rate_limit_delay=1.0):
    """
    Fetch the full plain text of an opinion by its ID.
    This is a separate API call from search, needed since search only returns a short snippet.
    """
    if not opinion_id or not COURTLISTENER_TOKEN:
        return ""

    time.sleep(rate_limit_delay)  # stay under free-tier rate limit

    headers = {"Authorization": f"Token {COURTLISTENER_TOKEN}"}
    url = COURTLISTENER_OPINION_URL.format(opinion_id)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch opinion {opinion_id}: {e}")
        return ""

    return data.get("plain_text", "")
    
def filter_relevant_court_records(applicant_name, results, name_match_threshold=85):
    """
    Fetch full opinion text for each result, then fuzzy-check whether the applicant's
    name is actually mentioned in the opinion body (not just the case caption,
    since named parties are often companies while the individual appears only in the text).
    """
    relevant = []
    for r in results:
        opinion_text = fetch_opinion_text(r.get("opinion_id"))
        r["opinion_text"] = opinion_text  # keep for keyword check + audit trail

        if not opinion_text:
            continue

        # partial_ratio finds the name as a substring within the long opinion text
        name_score = fuzz.partial_ratio(applicant_name.lower(), opinion_text.lower())

        if name_score >= name_match_threshold:
            r["name_match_score"] = name_score
            relevant.append(r)

    return relevant

def is_financially_relevant(record):
    """Check if a court record's case name or snippet suggests financial/compliance risk."""
    text = (record.get("case_name", "") + " " + record.get("opinion_text", "")).lower()
    matched_keywords = [kw for kw in FINANCIAL_RISK_KEYWORDS if kw in text]
    return len(matched_keywords) > 0, matched_keywords

def check_court_records(applicant_name, max_results=1, rate_limit_delay=1.0):
    """
    Full check: search CourtListener, fetch full opinion text for each hit,
    filter to name-relevant results, then split by financial/compliance risk.
    """
    time.sleep(rate_limit_delay)

    raw_results = search_court_records(applicant_name, max_results=max_results)
    name_matched_results = filter_relevant_court_records(applicant_name, raw_results)

    high_risk_records = []
    low_risk_records = []

    for r in name_matched_results:
        is_risky, keywords = is_financially_relevant(r)
        r["matched_keywords"] = keywords
        # Drop the full opinion_text from final output to keep it lean; keep only what's needed
        r.pop("opinion_text", None)
        if is_risky:
            high_risk_records.append(r)
        else:
            low_risk_records.append(r)

    return {
        "court_hit": len(high_risk_records) > 0,
        "raw_count": len(raw_results),
        "name_matched_count": len(name_matched_results),
        "high_risk_count": len(high_risk_records),
        "high_risk_records": high_risk_records,
        "low_risk_records": low_risk_records,
    }
    
if __name__ == "__main__":
    # Quick manual test
    test_name = "Sam Bankman-Fried"
    result = check_court_records(test_name)

    print(f"Applicant: {test_name}")
    print(f"Raw: {result['raw_count']}, Name-matched: {result['name_matched_count']}, High-risk: {result['high_risk_count']}")
    print("\nHigh-risk records:")
    for r in result["high_risk_records"]:
        print(f"- {r['case_name']} ({r['date_filed']}) - {r['url']} - Keywords: {', '.join(r['matched_keywords'])}")
    for r in result["low_risk_records"]:
        print(f"- {r['case_name']} ({r['date_filed']}) - {r['url']} - Keywords: {', '.join(r['matched_keywords'])}")

