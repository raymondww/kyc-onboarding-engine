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

# --- LangGraph pipeline ---
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

if __name__ == "__main__":
    # Quick manual test
    test_name = "Jane Doe"
    results = search_adverse_media(test_name)

    print(f"Found {len(results)} results for '{test_name}'")
    for r in results:
        print(f"- {r['title']}")
        print(f"  {r['body'][:150]}...")
        print(r)