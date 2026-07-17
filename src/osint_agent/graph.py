from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

from ofac_check import check_ofac_match, load_sdn_list
from search_news import search_adverse_media
from filters import filter_irrelevant_domains
from court_records_check import check_court_records
from summarize import summarize_risk


class AgentState(TypedDict):
    applicant_name: str
    applicant_dob: Optional[str]
    ofac_result: dict
    raw_results: list
    filtered_results: list
    court_result: dict
    risk_summary: str
    risk_flag: str

# Load once at module level, reused across all runs
_sdn_df = load_sdn_list()

def ofac_check_node(state: AgentState) -> AgentState:
    profile = {"full_name": state["applicant_name"], "dob": state["applicant_dob"]}
    state["ofac_result"] = check_ofac_match(profile, _sdn_df)
    return state


def route_after_ofac_check(state: AgentState) -> str:
    """Conditional edge: skip news search if OFAC match is already HIGH confidence."""
    result = state["ofac_result"]
    if result["ofac_hit"] and result["confidence"] == "HIGH":
        return "finalize_high_confidence"
    return "search"


def finalize_high_confidence_node(state: AgentState) -> AgentState:
    """Fast path: OFAC match alone is strong enough, skip news search entirely."""
    result = state["ofac_result"]
    state["risk_summary"] = (
        f"Exact name and date-of-birth match found on the OFAC SDN list "
        f"(matched entry: {result['matched_name']}). No further review needed."
    )
    state["risk_flag"] = "HIGH"
    return state

def search_node(state: AgentState) -> AgentState:
    state["raw_results"] = search_adverse_media(state["applicant_name"])
    return state


def filter_node(state: AgentState) -> AgentState:
    state["filtered_results"] = filter_irrelevant_domains(state["raw_results"])
    return state

def court_records_node(state: AgentState) -> AgentState:
    state["court_result"] = check_court_records(state["applicant_name"], max_results=1)
    return state

def summarize_node(state: AgentState) -> AgentState:
    result = summarize_risk(state["applicant_name"], state["filtered_results"])
    state["risk_summary"] = result["risk_summary"]
    state["risk_flag"] = result["risk_flag"]
    return state


# Build graph: search -> filter -> summarize
graph = StateGraph(AgentState)
graph.add_node("ofac_check", ofac_check_node)
graph.add_node("finalize_high_confidence", finalize_high_confidence_node)
graph.add_node("search", search_node)
graph.add_node("filter", filter_node)
graph.add_node("court_records", court_records_node)
graph.add_node("summarize", summarize_node)

graph.set_entry_point("ofac_check")
graph.add_conditional_edges(
    "ofac_check",
    route_after_ofac_check,
    {"finalize_high_confidence": "finalize_high_confidence", "search": "search"}
)
graph.add_edge("finalize_high_confidence", END)
graph.add_edge("search", "filter")
graph.add_edge("filter", "court_records")   # run court check after news filter
graph.add_edge("court_records", "summarize")
graph.add_edge("summarize", END)

app = graph.compile()