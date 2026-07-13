from typing import TypedDict
from langgraph.graph import StateGraph, END

from search_news import search_adverse_media
from filters import filter_irrelevant_domains
from summarize import summarize_risk


class AgentState(TypedDict):
    applicant_name: str
    raw_results: list
    filtered_results: list
    risk_summary: str
    risk_flag: str


def search_node(state: AgentState) -> AgentState:
    state["raw_results"] = search_adverse_media(state["applicant_name"])
    return state


def filter_node(state: AgentState) -> AgentState:
    state["filtered_results"] = filter_irrelevant_domains(state["raw_results"])
    return state


def summarize_node(state: AgentState) -> AgentState:
    result = summarize_risk(state["applicant_name"], state["filtered_results"])
    state["risk_summary"] = result["risk_summary"]
    state["risk_flag"] = result["risk_flag"]
    return state


# Build graph: search -> filter -> summarize
graph = StateGraph(AgentState)
graph.add_node("search", search_node)
graph.add_node("filter", filter_node)
graph.add_node("summarize", summarize_node)
graph.set_entry_point("search")
graph.add_edge("search", "filter")
graph.add_edge("filter", "summarize")
graph.add_edge("summarize", END)

app = graph.compile()