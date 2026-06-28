"""
Exposes the compiled LangGraph application maintaining backward compatibility
with app.py. Ensure no LLMs are globally instantiated here.
"""
from src.agents.graph import app


# import os
# from typing import List, Dict, Any, Literal

# from langchain_groq import ChatGroq
# from langchain_core.prompts import ChatPromptTemplate
# from langgraph.graph import StateGraph, START, END

# # Import Decoupled State, Prompts, and Tools
# from src.agents.state import GraphState, GradeResult
# from src.prompts.system_prompts import GRADER_SYSTEM_PROMPT, AUDIT_SYSTEM_PROMPT
# from src.tools.retriever import get_retriever
# from src.tools.search import execute_tavily_search
# from src.agents.graph import app

# # Initialize Groq LLM targeting production-grade Llama 3.3 model
# llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# # ==========================================
# # Graph Nodes
# # ==========================================

# def retrieve(state: GraphState) -> Dict[str, Any]:
#     """
#     Node: Queries the cached FAISS local database to isolate high-affinity legal documents.
#     """
#     question = state["question"]
#     steps = state.get("steps", [])
#     steps.append("retrieve_documents")
    
#     retriever = get_retriever()
#     docs = retriever.invoke(question)
#     doc_contents = [doc.page_content for doc in docs]
    
#     return {"documents": doc_contents, "steps": steps}

# def grade_documents(state: GraphState) -> Dict[str, Any]:
#     """
#     Node: Performs dynamic grading on the similarity chunks retrieved to evaluate 
#     if local contract facts are sufficient to analyze legal questions.
#     """
#     question = state["question"]
#     documents = state["documents"]
#     steps = state.get("steps", [])
#     steps.append("grade_documents")
    
#     grader_prompt = ChatPromptTemplate.from_messages([
#         ("system", GRADER_SYSTEM_PROMPT),
#         ("human", "User Query: {question}\n\nRetrieved Context:\n{context}")
#     ])
    
#     # Enforces structured extraction via Pydantic schema
#     chain = grader_prompt | llm.with_structured_output(GradeResult)
#     combined_context = "\n\n".join(documents)
    
#     try:
#         result = chain.invoke({"question": question, "context": combined_context})
#         score = result.score.upper().strip()
#     except Exception:
#         # Fallback to web search if the parsing execution drops
#         score = "NO"
        
#     return {"generation": score, "steps": steps}

# def web_search(state: GraphState) -> Dict[str, Any]:
#     """
#     Node: Activates the Corrective path, querying Indian labor code updates via Tavily.
#     """
#     question = state["question"]
#     steps = state.get("steps", [])
#     steps.append("execute_web_search")
    
#     enhanced_query = f"{question} Indian Labor Code 2026 ruling statute"
#     context = execute_tavily_search(enhanced_query)
    
#     return {"web_search_context": context, "steps": steps}

# def generate_audit(state: GraphState) -> Dict[str, Any]:
#     """
#     Node: Compiles and structures the compliance report citing relevant labor codes and verdicts.
#     """
#     question = state["question"]
#     documents = state["documents"]
#     web_context = state.get("web_search_context", "No external web data needed.")
#     steps = state.get("steps", [])
#     steps.append("generate_audit_report")
    
#     audit_prompt = ChatPromptTemplate.from_messages([
#         ("system", AUDIT_SYSTEM_PROMPT),
#         ("human", "Query: {question}\n\nInternal Company Context:\n{internal_context}\n\nExternal Legal Context:\n{external_context}")
#     ])
    
#     chain = audit_prompt | llm
#     response = chain.invoke({
#         "question": question,
#         "internal_context": "\n\n".join(documents),
#         "external_context": web_context
#     })
    
#     return {"generation": response.content, "steps": steps}

# # ==========================================
# # Routing Decisions
# # ==========================================

# def route_after_grading(state: GraphState) -> Literal["web_search", "generate_audit"]:
#     """
#     Conditional edge deciding whether the workflow proceeds to search or direct compilation.
#     """
#     if state["generation"] == "NO":
#          return "web_search"
#     return "generate_audit"

# # ==========================================
# # Building the DAG
# # ==========================================

# workflow = StateGraph(GraphState)

# # Add Nodes
# workflow.add_node("retrieve", retrieve)
# workflow.add_node("grade_documents", grade_documents)
# workflow.add_node("web_search", web_search)
# workflow.add_node("generate_audit", generate_audit)

# # Connect Edges
# workflow.add_edge(START, "retrieve")
# workflow.add_edge("retrieve", "grade_documents")
# workflow.add_conditional_edges(
#     "grade_documents",
#     route_after_grading
# )
# workflow.add_edge("web_search", "generate_audit")
# workflow.add_edge("generate_audit", END)

# app = workflow.compile()