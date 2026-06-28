from typing import List, Dict, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

class GraphState(TypedDict):
    """
    Defines the strict type layout for data circulating within the LangGraph state machine.
    """
    question: str
    documents: List[str]
    web_search_context: str
    corporate_defense: str
    generation: str
    judge_score: str
    judge_feedback: str
    revision_count: int
    steps: List[str]

class GradeResult(BaseModel):
    """Schema for document relevance grading."""
    score: str = Field(description="Binary relevance score. Must be strictly 'YES' or 'NO'.")

class JudgeResult(BaseModel):
    """Schema for the final Actor-Critic evaluation."""
    score: str = Field(description="Evaluation score. Must be strictly 'PASS' or 'FAIL'.")
    feedback: str = Field(description="Specific reason for failure, or 'PERFECT' if PASS.")