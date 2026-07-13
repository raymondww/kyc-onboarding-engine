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

# Build graph
graph = StateGraph(AgentState)
graph.add_node("search", search_node)
graph.add_node("filter", filter_node)
graph.set_entry_point("search")
graph.add_edge("search", "filter")
graph.add_edge("filter", END)
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