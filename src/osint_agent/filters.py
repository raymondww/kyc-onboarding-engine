def filter_irrelevant_domains(results):
    """
    Strip out sources that are almost never useful adverse-media signal:
    encyclopedias, dictionaries, generic reference sites.

    Returns the filtered list of result dicts.
    """
    blocked_domains = ["wikipedia.org", "dictionary.com", "merriam-webster.com", "wiktionary.org"]
    filtered = [r for r in results if not any(domain in r.get("href", "") for domain in blocked_domains)]
    return filtered


if __name__ == "__main__":
    # Quick manual test
    sample_results = [
        {"title": "Jane Doe - Wikipedia", "href": "https://en.wikipedia.org/wiki/Jane_Doe", "body": "..."},
        {"title": "Jane Doe fraud case", "href": "https://news-site.com/article", "body": "..."},
    ]
    filtered = filter_irrelevant_domains(sample_results)
    print(f"Before filtering: {len(sample_results)}")
    print(f"After filtering: {len(filtered)}")
    for r in filtered:
        print(f"- {r['title']}")