from typing import List, Dict, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langchain_core.documents import Document

class GraphState(TypedDict):
    """
    Defines the strict type layout for data circulating within the LangGraph state machine.
    """
    question: str
    documents: List[str]
    web_search_context: str
    generation: str
    steps: List[str]

class GradeResult(BaseModel):
    """
    Pydantic schema enforcing structured JSON extraction from the document grading node.
    """
    score: str = Field(
        description="Binary relevance score. Must be strictly 'YES' or 'NO'."
    )

class AgentState(TypedDict):
    user_query: str          # Textbox 1: "Can they hold my 10th marksheet?"
    employer_facts: str      # Textbox 2: "Clause 4: Original certificates will be held for 3 years..."
    documents: List[Document] # The FAISS retrieved heavy artillery
    web_search: bool         # The CRAG routing flag
    final_answer: str        # The lethal output