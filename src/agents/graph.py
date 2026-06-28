import os
from typing import List, Dict, Any, Literal

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

# Import Decoupled State, Prompts, and Tools
from src.agents.state import GraphState, GradeResult
from src.prompts.system_prompts import GRADER_SYSTEM_PROMPT, AUDIT_SYSTEM_PROMPT
from src.tools.retriever import get_retriever
from src.tools.search import execute_tavily_search
from src.utils.text_crusher import crush_corporate_noise

# ==========================================
# 1. Lazy Model Initialization Helpers
# ==========================================
def get_fast_llm() -> ChatGroq:
    """Lazily instantiates the fast utility model."""
    return ChatGroq(
        model="llama-3.1-8b-instant", 
        temperature=0,
        max_tokens=1000,
        api_key=os.environ.get("GROQ_API_KEY")
    )

def get_complex_llm() -> ChatGroq:
    """Lazily instantiates the complex analytical model."""
    return ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0,
        max_tokens=1500,
        api_key=os.environ.get("GROQ_API_KEY")
    )

# ==========================================
# 2. Token Budgeting Utility
# ==========================================
def truncate_text_to_budget(text_list: List[str], max_chars: int) -> str:
    combined = ""
    for text in text_list:
        clean_text = text.strip()
        if len(combined) + len(clean_text) + 2 > max_chars:
            remaining = max_chars - len(combined)
            if remaining > 150:
                combined += "\n\n" + clean_text[:remaining] + "... [Context Truncated for Rate Limits]"
            break
        combined += "\n\n" + clean_text
    return combined.strip()

# ==========================================
# 3. Graph Nodes
# ==========================================

def compress_query(state: GraphState) -> Dict[str, Any]:
    raw_question = state["question"]
    steps = state.get("steps", [])
    steps.append("compress_query")
    
    # 1. Zero-Cost Preprocessing: Distill the email chain/corporate noise
    distilled_question = crush_corporate_noise(raw_question)
    
    # 2. Skip LLM compression if the distilled text is already small enough
    if len(distilled_question) < 1200:
        return {"question": distilled_question, "steps": steps}
        
    compress_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an elite legal data extractor. The user has provided a raw, fragmented corporate communication or contract. "
                   "Your job is to radically distill this text into a pure timeline of facts, legal assertions, and the core compliance question. "
                   "OMIT all conversational filler, emotional language, greetings, and repetitive signatures. "
                   "Output ONLY the timeline of events and the specific legal/HR clauses under dispute. Keep it under 500 words."),
        ("human", "Crushed Input:\n{raw_input}")
    ])
    
    llm_fast = get_fast_llm()
    chain = compress_prompt | llm_fast
    
    # Cap input to stay within TPM boundaries
    truncated_input = distilled_question[:15000]
    
    try:
        response = chain.invoke({"raw_input": truncated_input})
        compressed_query = response.content.strip()
    except Exception:
        compressed_query = distilled_question[:3000]
        
    return {"question": compressed_query, "steps": steps}

def retrieve(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("retrieve_documents")
    
    retriever = get_retriever()
    docs = retriever.invoke(question)
    doc_contents = [doc.page_content for doc in docs]
    
    return {"documents": doc_contents, "steps": steps}

def grade_documents(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    documents = state["documents"]
    steps = state.get("steps", [])
    steps.append("grade_documents")
    
    grader_prompt = ChatPromptTemplate.from_messages([
        ("system", GRADER_SYSTEM_PROMPT),
        ("human", "User Query: {question}\n\nRetrieved Context:\n{context}")
    ])
    
    llm_fast = get_fast_llm()
    chain = grader_prompt | llm_fast.with_structured_output(GradeResult)
    
    combined_context = truncate_text_to_budget(documents, max_chars=6000)
    
    try:
        result = chain.invoke({"question": question, "context": combined_context})
        score = result.score.upper().strip()
    except Exception:
        score = "NO"
        
    return {"generation": score, "steps": steps}

def web_search(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("execute_web_search")
    
    enhanced_query = f"{question} Indian Labor Code 2026 ruling statute"
    context = execute_tavily_search(enhanced_query)
    
    return {"web_search_context": context, "steps": steps}

def generate_audit(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    documents = state["documents"]
    web_context_raw = state.get("web_search_context", "No external web data needed.")
    grade = state.get("generation", "YES") # Get the grader's decision
    steps = state.get("steps", [])
    steps.append("generate_audit_report")
    
    audit_prompt = ChatPromptTemplate.from_messages([
        ("system", AUDIT_SYSTEM_PROMPT),
        ("human", "Query: {question}\n\nInternal Company Context:\n{internal_context}\n\nExternal Legal Context:\n{external_context}")
    ])
    
    llm_complex = get_complex_llm()
    chain = audit_prompt | llm_complex
    
    # THE FIX: If the internal documents were useless, DO NOT feed them to the final LLM.
    if grade == "NO":
        internal_budget = "[SYSTEM LOG: INTERNAL DOCUMENTS DEEMED IRRELEVANT. LLM MUST RELY EXCLUSIVELY ON EXTERNAL LEGAL CONTEXT.]"
    else:
        internal_budget = truncate_text_to_budget(documents, max_chars=8000)
        
    external_budget = truncate_text_to_budget([web_context_raw], max_chars=4000)
    
    response = chain.invoke({
        "question": question,
        "internal_context": internal_budget,
        "external_context": external_budget
    })
    
    return {"generation": response.content, "steps": steps}

# ==========================================
# Routing Decisions
# ==========================================
def route_after_grading(state: GraphState) -> Literal["web_search", "generate_audit"]:
    if state["generation"] == "NO":
         return "web_search"
    return "generate_audit"

# ==========================================
# Building the DAG
# ==========================================
workflow = StateGraph(GraphState)

workflow.add_node("compress_query", compress_query)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate_audit", generate_audit)

workflow.add_edge(START, "compress_query")
workflow.add_edge("compress_query", "retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges("grade_documents", route_after_grading)
workflow.add_edge("web_search", "generate_audit")
workflow.add_edge("generate_audit", END)

app = workflow.compile()