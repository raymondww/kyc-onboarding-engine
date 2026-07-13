from ddgs import DDGS


def search_adverse_media(applicant_name, max_results=5):
    """
    Search DuckDuckGo for adverse media (fraud, sanctions, investigations)
    linked to the applicant's name.

    Returns a list of dicts: [{"title": ..., "href": ..., "body": ...}, ...]
    """
    query = f'"{applicant_name}" fraud OR sanctions OR investigation OR lawsuit'
    print(f"Searching for adverse media for: {query}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        print(f"Search failed for {applicant_name}: {e}")
        results = []

    return results


if __name__ == "__main__":
    # Quick manual test
    test_name = "Jane Doe"
    results = search_adverse_media(test_name)

    print(f"Found {len(results)} results for '{test_name}'")
    for r in results:
        print(f"- {r['title']}")
        print(f"  {r['body'][:150]}...")
        print(r)