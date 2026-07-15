import os
import time
import requests
from rapidfuzz import fuzz
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

COURTLISTENER_API_URL = "https://www.courtlistener.com/api/rest/v4/search/"
COURTLISTENER_TOKEN = os.environ.get("COURTLISTENER_API_TOKEN")  


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
            "snippet": item.get("snippet", "")
        })

    return results

if __name__ == "__main__":
    # Quick manual test
    test_name = "Jane Doe"
    result = search_court_records(test_name)

    print(f"Applicant: {test_name}")
    if result:
        print("Court Records Found:")
        for record in result:
            print(f"- Case Name: {record['case_name']}")
            print(f"  Date Filed: {record['date_filed']}")
            print(f"  URL: {record['url']}")
            print(f"  Snippet: {record['snippet']}\n")
    else:
        print("No court records found.")
