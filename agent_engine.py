import os
from typing import List, Dict, Any, Literal
from typing_extensions import TypedDict

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, START, END

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field


# ==========================================
# 1. State Definition
# ==========================================
class GraphState(TypedDict):
    question: str
    documents: List[str]
    web_search_context: str
    generation: str
    steps: List[str]

# ==========================================
# 2. Initialization & Tools
# ==========================================
# Initialize LLM via Groq (using Llama 3.3 for analytical depth)
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)

# Load the local FAISS DB built by your indexer
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = FAISS.load_local("faiss_legal_db", embeddings, allow_dangerous_deserialization=True)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

# Initialize Web Search Fallback
web_search_tool = TavilySearchResults(k=2)

# ==========================================
# 3. Graph Nodes
# ==========================================

def retrieve(state: GraphState) -> Dict[str, Any]:
    """Retrieves relevant chunks from the FAISS database."""
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("retrieve_documents")
    
    docs = retriever.invoke(question)
    doc_contents = [doc.page_content for doc in docs]
    
    return {"documents": doc_contents, "steps": steps}

def grade_documents(state: GraphState) -> Dict[str, Any]:
    """Evaluates if the retrieved chunks are sufficient to address the legal query."""
    question = state["question"]
    documents = state["documents"]
    steps = state.get("steps", [])
    steps.append("grade_documents")
    
    # Define the exact structure we want the LLM to output
    class GraderOutput(BaseModel):
        score: str = Field(description="Score indicating relevance. Must be exactly 'YES' or 'NO'.")

    # Structural prompt evaluating relevance
    grader_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert legal compliance auditor. Grade whether the provided context contains relevant facts, clauses, or policy definitions related to the user's query."),
        ("human", "User Query: {question}\n\nRetrieved Context: {context}")
    ])
    
    # Bind the Pydantic model to the LLM
    chain = grader_prompt | llm.with_structured_output(GraderOutput)
    
    combined_context = "\n\n".join(documents)
    try:
        result = chain.invoke({"question": question, "context": combined_context})
        score = result.score
    except Exception as e:
        print(f"Grader error: {e}")
        score = "NO"  # Fallback to web search if parsing fails
        
    return {"generation": score, "steps": steps}

def web_search(state: GraphState) -> Dict[str, Any]:
    """Fallback node to search Indian statutory frameworks using Tavily."""
    question = state["question"]
    steps = state.get("steps", [])
    steps.append("execute_web_search")
    
    # Enhance the query to target legal infrastructure explicitly
    legal_query = f"{question} Indian Labour Law Code 2026 judgment statute"
    
    # Pass string directly instead of a dictionary to avoid silent tool failures
    search_results = web_search_tool.invoke(legal_query)
    
    # Robust type handling: tools can return lists of dicts, strings (errors/JSON), or lists of strings
    if isinstance(search_results, str):
        context = search_results
    elif isinstance(search_results, list):
        context = "\n".join([
            res.get("content", "") if isinstance(res, dict) else str(res)
            for res in search_results
        ])
    else:
        context = str(search_results)
        
    return {"web_search_context": context, "steps": steps}

def generate_audit(state: GraphState) -> Dict[str, Any]:
    """Compiles the audit report citing relevant statutes and highlighting inconsistencies."""
    question = state["question"]
    documents = state["documents"]
    web_context = state.get("web_search_context", "No external web data needed.")
    steps = state.get("steps", [])
    steps.append("generate_audit_report")
    
    audit_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a critical legal compliance officer auditing internal corporate contracts.\n"
                   "Compare the internal company documents against standard Indian Labour laws (such as Code on Wages 2019, Industrial Relations Code 2020).\n"
                   "Provide a transparent compliance report. Identify non-compliant terms, name the explicit Act violated, and provide quotes."),
        ("human", "Query: {question}\n\nInternal Company Context:\n{internal_context}\n\nExternal Legal Context:\n{external_context}")
    ])
    
    chain = audit_prompt | llm
    response = chain.invoke({
        "question": question,
        "internal_context": "\n\n".join(documents),
        "external_context": web_context
    })
    
    return {"generation": response.content, "steps": steps}

# ==========================================
# 4. Conditional Routing Logic
# ==========================================
def route_after_grading(state: GraphState) -> Literal["web_search", "generate_audit"]:
    """Determines whether to trigger external web execution based on the grader's evaluation."""
    if state["generation"] == "NO":
        return "web_search"
    return "generate_audit"

# ==========================================
# 5. Graph Compilation
# ==========================================
workflow = StateGraph(GraphState)

# Add Nodes
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate_audit", generate_audit)

# Build Edges
workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges(
    "grade_documents",
    route_after_grading
)
workflow.add_edge("web_search", "generate_audit")
workflow.add_edge("generate_audit", END)

# Compile Application Runtime
app = workflow.compile()