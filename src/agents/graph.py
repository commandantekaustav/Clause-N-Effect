import os
from typing import List, Dict, Any, Literal, cast, Union
from pydantic import SecretStr

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
from src.tools.gold_store import get_similar_success, save_successful_audit
from src.utils.pii_scrubber import scrub_pii

# ==========================================
# 1. HYBRID BRAIN: Model Initialization
# ==========================================
def get_fast_llm() -> ChatGroq:
    key = os.environ.get("GROQ_API_KEY")
    return ChatGroq(
        model="llama-3.1-8b-instant", 
        temperature=0,
        max_tokens=2048, 
        api_key=SecretStr(key) if key else None
    )

def get_complex_llm() -> ChatGroq:
    key = os.environ.get("GROQ_API_KEY")
    return ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0.2, 
        max_tokens=1500,
        api_key=SecretStr(key) if key else None
    )

def truncate_text_to_budget(text_list: List[str], max_chars: int) -> str:
    combined = ""
    for text in text_list:
        clean_text = str(text).strip()
        if len(combined) + len(clean_text) + 2 > max_chars:
            remaining = max_chars - len(combined)
            if remaining > 150:
                combined += "\n\n" + clean_text[:remaining] + "... [Truncated]"
            break
        combined += "\n\n" + clean_text
    return combined.strip()

# ==========================================
# 2. Graph Nodes
# ==========================================

def compress_query(state: GraphState) -> Dict[str, Any]:
    raw_question = state["question"]
    scrubbed_question = scrub_pii(raw_question)
    steps = state.get("steps", [])
    steps.append("compress_query")
    
    if len(scrubbed_question) < 400:
        return {"question": scrubbed_question, "steps": steps}
        
    compress_prompt = ChatPromptTemplate.from_messages([
        ("system", "Distill the following into a timeline of facts and the core legal question. Max 1000 words."),
        ("human", "{raw_input}")
    ])
    
    chain = compress_prompt | get_fast_llm()
    try:
        response = chain.invoke({"raw_input": scrubbed_question[:15000]})
        compressed_query = str(response.content).strip()
    except Exception:
        compressed_query = scrubbed_question[:3000]
        
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
        result = cast(GradeResult, chain.invoke({"question": question, "context": combined}))
        score = result.score.upper().strip()
    except Exception:
        score = "NO"
        
    return {"generation": score, "steps": steps}

def web_search(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("execute_web_search")
    
    context = execute_tavily_search(f"{question} Indian labor law statute")
    return {"web_search_context": context, "steps": steps}

def draft_corporate_defense(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("draft_corporate_defense")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", CORPORATE_DEFENSE_PROMPT),
        ("human", "Facts:\n{question}")
    ])
    
    response = get_fast_llm().invoke(prompt.format_messages(question=question))
    return {"corporate_defense": str(response.content), "steps": steps}

def generate_audit(state: GraphState) -> Dict[str, Any]:
    question = state["question"]
    gender = state.get("gender", "not specified")
    work_state = state.get("work_state", "India")
    is_manager = state.get("is_manager", False)
    role_type_string = "Managerial" if is_manager else "Non-Managerial"

    documents = state.get("documents", [])
    web_context = state.get("web_search_context", "No external context.")
    corporate_defense = state.get("corporate_defense", "")
    judge_feedback = state.get("judge_feedback", "None")
    
    steps = state.get("steps", [])
    steps.append("generate_audit_report")
    
    # FETCH GOLD STANDARD MEMORY
    gold_example = get_similar_success(question)
    
    internal_budget = truncate_text_to_budget(documents, max_chars=8000)
    external_budget = truncate_text_to_budget([web_context], max_chars=4000)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", AUDIT_SYSTEM_PROMPT),
        ("human", "REFERENCE CASE:\n{example}\n\nCURRENT CASE DATA:\nFacts: {question}\nInternal Law: {internal}\nWeb Search: {external}\nCorporate Defense: {defense}\nJudge Feedback: {feedback}")
    ])

    chain = prompt | get_complex_llm()
    response = chain.invoke({
        "example": gold_example,
        "question": question,
        "internal": internal_budget,
        "external": external_budget,
        "defense": corporate_defense,
        "feedback": judge_feedback,
        "gender": gender,
        "work_state": work_state,
        "role_type": role_type_string
    })
    
    return {"generation": str(response.content), "steps": steps}

def evaluate_audit(state: GraphState) -> Dict[str, Any]:
    generation = state.get("generation", "")
    raw_facts = state.get("question", "")
    gender = state.get("gender", "unknown").lower()
    revision_count = state.get("revision_count", 0)
    rejection_reasons = state.get("rejection_reasons", [])
    steps = state.get("steps", [])
    steps.append("evaluate_audit")

    # 1. HARD-CODED PYTHON CHECK (ZERO Hallucination for Gender)
    if gender == "male":
        posh_triggers = ["POSH", "Sexual Harassment", "Internal Complaints Committee", "ICC"]
        if any(t.lower() in generation.lower() for t in posh_triggers):
            msg = "GENDER-STATUTE MISMATCH: Report cited POSH for a male user."
            return {
                "judge_score": "FAIL",
                "judge_feedback": msg,
                "revision_count": revision_count + 1,
                "rejection_reasons": rejection_reasons + [msg],
                "steps": steps
            }

    # 2. LLM JUDGE CHECK (For tone and evidence)
    prompt = ChatPromptTemplate.from_messages([
        ("system", JUDGE_SYSTEM_PROMPT),
        ("human", "Audit: {audit}\nRaw Evidence: {raw_facts}")
    ])
    
    chain = prompt | get_fast_llm().with_structured_output(JudgeResult)
    
    try:
        # Pass context correctly to the Judge
        result = cast(JudgeResult, chain.invoke({
            "audit": generation, 
            "user_gender": gender, 
            "raw_facts": raw_facts
        }))
        score = result.score.upper().strip()
        feedback = result.feedback
    except Exception as e:
        score = "FAIL"
        feedback = f"Judge Error: {str(e)}"
        
    if score == "PASS":
        save_successful_audit(raw_facts, generation)
    else:
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
def route_after_grading(state: GraphState) -> str:
    if state["generation"] == "NO":
         return "web_search"
    return "draft_corporate_defense"

def route_after_evaluation(state: GraphState) -> str:
    if state["judge_score"] == "PASS" or state.get("revision_count", 0) >= 3:
        return "end"
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

workflow.add_conditional_edges(
    "grade_documents",
    route_after_grading,
    {
        "web_search": "web_search",
        "draft_corporate_defense": "draft_corporate_defense"
    }
)

workflow.add_edge("web_search", "draft_corporate_defense")
workflow.add_edge("draft_corporate_defense", "generate_audit")
workflow.add_edge("generate_audit", "evaluate_audit")

workflow.add_conditional_edges(
    "evaluate_audit",
    route_after_evaluation,
    {
        "generate_audit": "generate_audit",
        "end": END
    }
)

app = workflow.compile()