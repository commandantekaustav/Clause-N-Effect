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
from src.utils.text_crusher import crush_corporate_noise

# ==========================================
# 1. HYBRID BRAIN: Lazy Model Initialization
# ==========================================
def get_fast_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.1-8b-instant", # The 8B workhorse for tasks (30,000 TPM limit)
        temperature=0,
        max_tokens=2048, # Increased to prevent text cutoffs!
        api_key=os.environ.get("GROQ_API_KEY")
    )

def get_complex_llm() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile", # The 70B genius for the Audit (6,000 TPM limit)
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
    steps = state.get("steps", [])
    steps.append("compress_query")
    
    distilled_question = raw_question.strip()
    
    if len(distilled_question) < 400:
        return {"question": distilled_question, "steps": steps}
        
    compress_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an investigative HR and Legal data extractor. Distill the provided text into a timeline of facts and the core compliance question. 
        
        CRITICAL DIRECTIVES:
        1. METADATA FORENSICS (CRITICAL): Pay extremely close attention to the To, Cc, and Bcc fields in the emails. If an employee Bcc's their personal email address, this is a MASSIVE red flag indicating fear of retaliation and the creation of a defensive paper trail. You MUST extract and highlight this behavior if present.
        2. HR & POWER DYNAMICS: You MUST explicitly capture any signs of workplace coercion, toxic power dynamics, reluctance, or defensive behaviors (forced agreements, impossible deadlines, top-down pressure). Do not sanitize human conflict.
        3. RAW EVIDENCE QUOTES: You MUST extract and preserve the exact, word-for-word text of any emails, company policies, or employer clauses. Put them under a clear heading called 'RAW EVIDENCE QUOTES'. Do NOT summarize direct dialogue.
        4. Max 1500 words."""),
        ("human", "Raw Input:\n{raw_input}")
    ])
    
    # Using 8B here is safe because we gave it 2048 tokens and strict metadata instructions
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
        
            Examples:
            Input: Must we translate contracts to local language?
            Output: India Shops Establishments Act contract language

            CRITICAL: If the query is about a toxic boss, coercion, unrealistic deadlines, or workplace pressure, DO NOT use the word "harassment". 
            Instead, output EXACTLY: "India Industrial Disputes Act Unfair Labour Practices"
            
            Output ONLY the search query text without quotes or explanations."""),
        ("human", "{question}")
    ])
    
    try:
        chain = query_prompt | get_fast_llm()
        search_query = chain.invoke({"question": question}).content.strip().replace('"', '')
    except Exception as e:
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
    documents = state.get("documents", [])
    web_context = state.get("web_search_context", "No external context.")
    corporate_defense = state.get("corporate_defense", "")
    judge_feedback = state.get("judge_feedback", "None")
    
    # --- NEW: The Do-or-Die Warning ---
    revision_count = state.get("revision_count", 0)
    if revision_count >= 2:
        judge_feedback = f"CRITICAL FINAL WARNING: You have failed formatting {revision_count} times. You MUST strictly use the exact Markdown skeleton and exact HTML span tags, or the system will crash. Previous error: " + judge_feedback

    steps = state.get("steps", [])
    steps.append("generate_audit_report")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", AUDIT_SYSTEM_PROMPT),
        ("human", "Query/Facts: {question}\n\nInternal Legal DB: {internal}\n\nWeb Statutes: {external}\n\nCorporate Defense To Destroy: {defense}\n\nPrevious Judge Feedback to Fix: {feedback}")
    ])
    
    if state.get("generation") == "NO":
        internal_budget = "[INTERNAL DB REJECTED OR EMPTY - YOU MUST RELY EXCLUSIVELY ON EXTERNAL LEGAL CONTEXT OR INTERNAL PRE-TRAINED KNOWLEDGE.]"
    else:
        internal_budget = truncate_text_to_budget(documents, max_chars=10000)
        
    external_budget = truncate_text_to_budget([web_context], max_chars=6000)
    
    # THIS IS THE ONLY NODE THAT USES THE EXPENSIVE 70B MODEL
    chain = prompt | get_complex_llm()
    response = chain.invoke({
        "question": question,
        "internal": internal_budget,
        "external": external_budget,
        "defense": corporate_defense,
        "feedback": judge_feedback
    })
    
    return {"generation": response.content, "steps": steps}

def evaluate_audit(state: GraphState) -> Dict[str, Any]:
    generation = state["generation"]
    steps = state.get("steps", [])
    revision_count = state.get("revision_count", 0)
    
    steps.append("evaluate_audit")
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", JUDGE_SYSTEM_PROMPT),
        ("human", "Generated Audit:\n{audit}")
    ])
    
    # 8B is perfectly fine here. It just acts as a Regex checker for Markdown formatting.
    chain = prompt | get_fast_llm().with_structured_output(JudgeResult)
    
    try:
        result = chain.invoke({"audit": generation})
        score = result.score.upper().strip()
        feedback = result.feedback
    except Exception as e:
        score = "FAIL" 
        feedback = f"Judge API threw an error. Generator MUST stick exactly to the Skeleton Format and use HTML span tags."
        
    return {
        "judge_score": score, 
        "judge_feedback": feedback, 
        "revision_count": revision_count + 1,
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
workflow.add_edge("grade_documents", "web_search")
workflow.add_edge("web_search", "draft_corporate_defense")
workflow.add_edge("draft_corporate_defense", "generate_audit")
workflow.add_edge("generate_audit", "evaluate_audit")
workflow.add_conditional_edges("evaluate_audit", route_after_evaluation)

app = workflow.compile()