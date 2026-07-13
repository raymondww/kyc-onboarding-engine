from ddgs import DDGS
from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from typing import TypedDict

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

def filter_irrelevant_domains(results):
    """
    Strip out sources that are almost never useful adverse-media signal:
    encyclopedias, dictionaries, generic reference sites.
    """
    print(f"Filtering {len(results)} results for irrelevant domains...")
    blocked_domains = ["wikipedia.org", "dictionary.com", "merriam-webster.com", "wiktionary.org"]
    filtered = [r for r in results if not any(domain in r.get("href", "") for domain in blocked_domains)]
    return filtered

# LangGraph pipeline 
class AgentState(TypedDict):
    applicant_name: str
    raw_results: list
    filtered_results: list
    risk_summary: str
    risk_flag: str

llm = ChatOllama(model="gemma4:e4b", temperature=0)

def search_node(state: AgentState) -> AgentState:
    state["raw_results"] = search_adverse_media(state["applicant_name"])
    return state


def filter_node(state: AgentState) -> AgentState:
    state["filtered_results"] = filter_irrelevant_domains(state["raw_results"])
    return state

def summarize_node(state: AgentState) -> AgentState:
    """
    Ask the LLM to (1) judge relevance of each result to this specific applicant,
    (2) summarize risk using only relevant results, (3) assign a flag.
    """
    print(f"Summarizing {len(state['filtered_results'])} filtered results for {state['applicant_name']}...")
    results = state["filtered_results"]

    if not results:
        state["risk_summary"] = "No adverse media found in public search results."
        state["risk_flag"] = "LOW"
        return state

    articles_text = "\n".join(
        [f"- {r['title']}: {r['body'][:200]}" for r in results]
    )

    prompt = f"""You are a compliance analyst reviewing public search results about an applicant named {state['applicant_name']}.

    Search results:
    {articles_text}

    Step 1: For each result, judge whether it plausibly refers to THIS specific applicant, or could be about an unrelated person who shares the same name. Note any signs it's likely a different person (e.g. a generic biography, an unrelated profession, no financial/legal context).

    Step 2: Based only on results you judged as plausibly relevant, write a 2-3 sentence risk summary.

    Step 3: Classify the overall risk as LOW, MEDIUM, or HIGH. If no results were judged relevant, this should be LOW. End your response with exactly "FLAG: <level>".
    """

    response = llm.invoke(prompt)
    content = response.content

    flag = "HIGH" if "FLAG: HIGH" in content else "MEDIUM" if "FLAG: MEDIUM" in content else "LOW"
    state["risk_summary"] = content
    state["risk_flag"] = flag
    return state

# Build graph
graph = StateGraph(AgentState)
graph.add_node("search", search_node)
graph.add_node("filter", filter_node)
graph.add_node("summarize", summarize_node)
graph.set_entry_point("search")
graph.add_edge("search", "filter")
graph.add_edge("filter", "summarize")
graph.add_edge("summarize", END)
app = graph.compile()

def run_osint_agent(applicant_name):
    """Convenience wrapper to run the full pipeline for one applicant."""
    result = app.invoke({
        "applicant_name": applicant_name,
        "raw_results": [],
        "filtered_results": [],
        "risk_summary": "",
        "risk_flag": ""
    })
    return result

if __name__ == "__main__":
    # Quick manual test
    test_name = "Jane Doe"
    # results = search_adverse_media(test_name)
    
    result = run_osint_agent(test_name)

    print(f"\nApplicant: {test_name}")
    print(f"Raw results found: {len(result['raw_results'])}")
    print(f"After filtering: {len(result['filtered_results'])}")
    print(f"\nRisk summary:\n{result['risk_summary']}")
    print(f"\nRisk flag: {result['risk_flag']}")