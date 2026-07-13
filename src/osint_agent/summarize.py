from langchain_ollama import ChatOllama

llm = ChatOllama(model="gemma4:e4b", temperature=0)


def summarize_risk(applicant_name, filtered_results):
    """
    Ask the LLM to (1) judge relevance of each result to this specific applicant,
    (2) summarize risk using only relevant results, (3) assign a flag.

    Returns a dict: {"risk_summary": str, "risk_flag": "LOW" | "MEDIUM" | "HIGH"}
    """
    if not filtered_results:
        return {
            "risk_summary": "No adverse media found in public search results.",
            "risk_flag": "LOW"
        }

    articles_text = "\n".join(
        [f"- {r['title']}: {r['body'][:200]}" for r in filtered_results]
    )

    prompt = f"""You are a compliance analyst reviewing public search results about an applicant named {applicant_name}.

    Search results:
    {articles_text}

    Step 1: For each result, judge whether it plausibly refers to THIS specific applicant, or could be about an unrelated person who shares the same name. Note any signs it's likely a different person (e.g. a generic biography, an unrelated profession, no financial/legal context).

    Step 2: Based only on results you judged as plausibly relevant, write a 2-3 sentence risk summary.

    Step 3: Classify the overall risk as LOW, MEDIUM, or HIGH. If no results were judged relevant, this should be LOW. End your response with exactly "FLAG: <level>".
    """

    response = llm.invoke(prompt)
    content = response.content

    flag = "HIGH" if "FLAG: HIGH" in content else "MEDIUM" if "FLAG: MEDIUM" in content else "LOW"

    return {"risk_summary": content, "risk_flag": flag}


if __name__ == "__main__":
    # Quick manual test
    sample_results = [
        {"title": "Viktor Kessler linked to shell company fraud investigation",
         "body": "Regulators are investigating Viktor Kessler for his alleged role in a money laundering scheme."},
    ]
    result = summarize_risk("Viktor Kessler", sample_results)
    print(result["risk_summary"])
    print(f"\nRisk flag: {result['risk_flag']}")