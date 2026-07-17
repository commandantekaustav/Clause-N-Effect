import os
from typing import List, Dict, Any, Literal

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END

from src.agents.state import GraphState, GradeResult, JudgeResult
from src.prompts.system_prompts import (
    GRADER_SYSTEM_PROMPT, AUDIT_SYSTEM_PROMPT, 
    CORPORATE_DEFENSE_PROMPT, JUDGE_SYSTEM_PROMPT
)
from src.tools.retriever import get_retriever
from src.tools.search import execute_tavily_search

from src.utils.pii_scrubber import scrub_pii

# ==========================================
# 1. HYBRID BRAIN: Lazy Model Initialization
# ==========================================
def get_fast_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.1-8b-instant", 
        temperature=0,
        max_tokens=2048, 
        api_key=os.environ.get("GROQ_API_KEY")
    )

def get_complex_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.2, 
        max_tokens=1500,
        api_key=os.environ.get("GROQ_API_KEY")
    )

def truncate_text_to_budget(text_list: List[str], max_chars: int) -> str:
    combined = ""
    for text in text_list:
        clean_text = text.strip()
        if len(combined) + len(clean_text) + 2 > max_chars:
            remaining = max_chars - len(combined)
            if remaining > 150:
                combined += "\n\n" + clean_text[:remaining] + "... [Context Truncated]"
            break
        combined += "\n\n" + clean_text
    return combined.strip()

# ==========================================
# 2. Graph Nodes
# ==========================================
def compress_query(state: GraphState) -> Dict[str, Any]:
    raw_question = state["question"]

    # SCRUB FIRST
    scrubbed_question = scrub_pii(raw_question)
    
    steps = state.get("steps", [])
    steps.append("compress_query")
    
    distilled_question = scrubbed_question.strip()
    
    if len(distilled_question) < 400:
        return {"question": distilled_question, "steps": steps}
        
    compress_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an investigative HR and Legal data extractor. Distill the provided text into a timeline of facts and the core compliance question. 
        
        CRITICAL DIRECTIVES:
        1. METADATA FORENSICS: Highlight Bcc usage, executive CCs, and timeline delays.
        2. HR & POWER DYNAMICS: Capture signs of coercion, forced agreements, and impossible deadlines.
        3. RAW EVIDENCE QUOTES: Extract verbatim text of emails under a clear heading 'RAW EVIDENCE QUOTES'.
        4. Max 1500 words."""),
        ("human", "Raw Input:\n{raw_input}")
    ])
    
    chain = compress_prompt | get_fast_llm()
    try:
        response = chain.invoke({"raw_input": distilled_question[:15000]})
        compressed_query = response.content.strip()
    except Exception:
        compressed_query = distilled_question[:3000]
        
    return {"question": compressed_query, "steps": steps}

def retrieve(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("retrieve_documents")
    
    docs = get_retriever().invoke(question)
    return {"documents": [doc.page_content for doc in docs], "steps": steps}

def grade_documents(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    documents = state["documents"]
    steps = state.get("steps", [])
    steps.append("grade_documents")
    
    if not documents:
        return {"generation": "NO", "steps": steps}
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", GRADER_SYSTEM_PROMPT),
        ("human", "Query: {question}\n\nContext:\n{context}")
    ])
    
    chain = prompt | get_fast_llm().with_structured_output(GradeResult)
    combined = truncate_text_to_budget(documents, max_chars=10000)
    
    try:
        result = chain.invoke({"question": question, "context": combined})
        score = result.score.upper().strip()
    except Exception:
        score = "NO"
        
    return {"generation": score, "steps": steps}

def web_search(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("execute_web_search")
    
    query_prompt = ChatPromptTemplate.from_messages([
        ("system", """Convert the HR compliance issue into a highly targeted, 4-6 word Google search query to find the exact Indian governing statute. 
            Output ONLY the search query text without quotes or explanations."""),
        ("human", "{question}")
    ])
    
    try:
        chain = query_prompt | get_fast_llm()
        search_query = chain.invoke({"question": question}).content.strip().replace('"', '')
    except Exception:
        search_query = question[:100].strip() + " India labour law statute"
        
    context = execute_tavily_search(search_query)
    return {"web_search_context": f"[AGENT SEARCH QUERY EXECUTED: {search_query}]\n\n{context}", "steps": steps}

def draft_corporate_defense(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("draft_corporate_defense")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", CORPORATE_DEFENSE_PROMPT),
        ("human", "Employee Query & Facts:\n{question}")
    ])
    
    chain = prompt | get_fast_llm()
    response = chain.invoke({"question": question})
    
    return {"corporate_defense": response.content, "steps": steps}

def generate_audit(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    gender = state.get("gender", "Not Specified")
    work_state = state.get("work_state", "India")
    is_manager = state.get("is_manager", False)

    role_type_string = "Managerial (Contract Act applies)" if is_manager else "Non-Managerial (Workman status possible)"

    documents = state.get("documents", [])
    web_context = state.get("web_search_context", "No external context.")
    corporate_defense = state.get("corporate_defense", "")
    judge_feedback = state.get("judge_feedback", "None")
    
    revision_count = state.get("revision_count", 0)
    if revision_count >= 2:
        judge_feedback = f"CRITICAL FINAL WARNING: You have failed formatting {revision_count} times. You MUST strictly use the exact Markdown skeleton and use Markdown blockquotes (>) for evidence. Previous error: " + judge_feedback

    steps = state.get("steps", [])
    steps.append("generate_audit_report")
    
    if state.get("generation") == "NO":
        internal_budget = "[INTERNAL DB REJECTED OR EMPTY - RELY ON EXTERNAL CONTEXT.]"
    else:
        internal_budget = truncate_text_to_budget(documents, max_chars=10000)
        
    external_budget = truncate_text_to_budget([web_context], max_chars=6000)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", AUDIT_SYSTEM_PROMPT),
        ("human", "Query/Facts: {question}\n\nInternal Legal DB: {internal}\n\nWeb Statutes: {external}\n\nCorporate Defense To Destroy: {defense}\n\nPrevious Judge Feedback to Fix: {feedback}")
    ])

    chain = prompt | get_complex_llm()
    response = chain.invoke({
        "question": question,
        "internal": internal_budget,
        "external": external_budget,
        "defense": corporate_defense,
        "feedback": judge_feedback,
        "gender": gender,
        "work_state": work_state,
        "role_type": role_type_string
    })
    
    return {"generation": response.content, "steps": steps}

def evaluate_audit(state: GraphState) -> Dict[str, Any]:
    generation = state["generation"]
    revision_count = state.get("revision_count", 0)
    
    # FIX: Explicitly get these from state so they are defined in this scope
    rejection_reasons = state.get("rejection_reasons", [])
    steps = state.get("steps", [])
    steps.append("evaluate_audit")
    
    # 1. HARD CODED RELIABILITY: Check for Unions in Python
    if "[NON-COMPLIANT]" in generation:
        unions = ["NITES", "KITU", "AIITEU"]
        if not any(u in generation for u in unions):
            feedback = "Missing Indian IT Unions in Retaliation Strategy."
            rejection_reasons.append(feedback)
            return {
                "judge_score": "FAIL",
                "judge_feedback": feedback,
                "revision_count": revision_count + 1,
                "rejection_reasons": rejection_reasons,
                "steps": steps
            }

    # 2. STANDARD LLM JUDGE CHECK
    prompt = ChatPromptTemplate.from_messages([
        ("system", JUDGE_SYSTEM_PROMPT),
        ("human", "Generated Audit:\n{audit}")
    ])
    
    chain = prompt | get_fast_llm().with_structured_output(JudgeResult)
    
    try:
        result = chain.invoke({"audit": generation})
        score = result.score.upper().strip()
        feedback = result.feedback
        if score == "FAIL":
            rejection_reasons.append(feedback)
    except Exception as e:
        score = "FAIL" 
        feedback = f"Judge API error: {str(e)}"
        rejection_reasons.append(feedback)        
        
    return {
        "judge_score": score, 
        "judge_feedback": feedback, 
        "revision_count": revision_count + 1,
        "rejection_reasons": rejection_reasons,
        "steps": steps
    }

# ==========================================
# 3. Routing Decisions
# ==========================================
def route_after_grading(state: GraphState) -> Literal["web_search", "draft_corporate_defense"]:
    if state["generation"] == "NO":
         return "web_search"
    return "draft_corporate_defense"

def route_after_evaluation(state: GraphState) -> Literal["generate_audit", END]:
    if state["judge_score"] == "PASS" or state["revision_count"] >= 3:
        return END
    return "generate_audit"

# ==========================================
# 4. Building the DAG
# ==========================================
workflow = StateGraph(GraphState)

workflow.add_node("compress_query", compress_query)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("draft_corporate_defense", draft_corporate_defense)
workflow.add_node("generate_audit", generate_audit)
workflow.add_node("evaluate_audit", evaluate_audit)

workflow.add_edge(START, "compress_query")
workflow.add_edge("compress_query", "retrieve")
workflow.add_edge("retrieve", "grade_documents")

# NEW CONDITIONAL ROUTE: Skip search if docs are good
workflow.add_conditional_edges(
    "grade_documents",
    route_after_grading, # We already have this function, but let's fix it
    {
        "web_search": "web_search",
        "draft_corporate_defense": "draft_corporate_defense"
    }
)

workflow.add_edge("web_search", "draft_corporate_defense")
workflow.add_edge("draft_corporate_defense", "generate_audit")

workflow.add_edge("web_search", "draft_corporate_defense")
workflow.add_edge("draft_corporate_defense", "generate_audit")
workflow.add_edge("generate_audit", "evaluate_audit")
workflow.add_conditional_edges("evaluate_audit", route_after_evaluation)

app = workflow.compile()