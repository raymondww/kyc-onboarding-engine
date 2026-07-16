import os
import time
import requests
from rapidfuzz import fuzz
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

COURTLISTENER_API_URL = "https://www.courtlistener.com/api/rest/v4/search/"
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
        results.append({
            "case_name": item.get("caseName", ""),
            "date_filed": item.get("dateFiled", ""),
            "url": f"https://www.courtlistener.com{item.get('absolute_url', '')}",
            "snippet": item["opinions"][0].get("snippet", "")
        })
    return results

def filter_relevant_court_records(applicant_name, results, name_match_threshold=85):
    """
    Check whether the applicant's name is actually mentioned in the case,
    using the opinion snippet as the primary evidence (not just case_name,
    since the named parties in a case title are often companies, not individuals,
    even when the individual is discussed at length in the opinion itself).
    """
    relevant = []
    for r in results:
        case_name = r.get("case_name", "")
        snippet = r.get("snippet", "")
        print(f"Snippet: {snippet}")
        print(r.get("url", ""))

        # Check if the applicant's name appears in the snippet text directly
        # partial_ratio handles cases where snippet has extra text around the name
        snippet_score = fuzz.partial_ratio(applicant_name.lower(), snippet.lower())
        case_name_score = fuzz.partial_ratio(applicant_name.lower(), case_name.lower())

        # Use whichever is higher, but snippet is the more reliable signal
        best_score = max(snippet_score, case_name_score)

        if best_score >= name_match_threshold:
            r["name_match_score"] = best_score
            r["matched_in"] = "snippet" if snippet_score >= case_name_score else "case_name"
            relevant.append(r)

    return relevant

def is_financially_relevant(record):
    """Check if a court record's case name or snippet suggests financial/compliance risk."""
    text = (record.get("case_name", "") + " " + record.get("snippet", "")).lower()
    matched_keywords = [kw for kw in FINANCIAL_RISK_KEYWORDS if kw in text]
    return len(matched_keywords) > 0, matched_keywords
 
if __name__ == "__main__":
    # Quick manual test
    test_name = "Sam Bankman-Fried"
    results = search_court_records(test_name)
    result = filter_relevant_court_records(test_name,results)
 
    print(f"Applicant: {test_name}")
    print(result)

