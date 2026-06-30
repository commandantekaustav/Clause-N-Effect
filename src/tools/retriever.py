import os
from typing import List, Any
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

# Process-level caching to prevent redundant I/O and memory overhead
_embeddings = None
_vectorstore = None
_cross_encoder = None

class ContextualRerankingRetriever:
    """
    Custom high-precision re-ranking retriever.
    Combines semantic bi-encoder vector retrieval with a cross-encoder attention model
    to rank retrieved chunks by strict logical relevance rather than syntax alone.
    """
    def __init__(self, base_retriever: Any, cross_encoder: Any, top_n: int = 2):
        self.base_retriever = base_retriever
        self.cross_encoder = cross_encoder
        self.top_n = top_n

    def invoke(self, query: str) -> List[Any]:
        # Step 1: Perform broad semantic sweep (high recall, k=15)
        docs = self.base_retriever.invoke(query)
        if not docs:
            return []

        # Step 2: Build attention pairs [Query, Document Text]
        pairs = [[query, doc.page_content] for doc in docs]

        # Step 3: Compute cross-attention logical entailment scores
        scores = self.cross_encoder.score(pairs)

        # Step 4: Sort documents by descending cross-encoder relevance scores
        scored_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

        # Step 5: Filter down to the top_n most contextually similar chunks
        top_docs = [doc for doc, score in scored_docs[:self.top_n]]
        return top_docs

def get_retriever():
    """
    Loads and caches the local FAISS retriever and the Cross-Encoder model.
    Returns a custom contextual re-ranking interface.
    """
    global _embeddings, _vectorstore, _cross_encoder
    
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
    if _vectorstore is None:
        db_path = "faiss_legal_db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"FAISS database directory '{db_path}' not found at the root level. "
                "Ensure that 'build_vector_db.py' has executed successfully."
            )
        _vectorstore = FAISS.load_local(
            db_path, 
            _embeddings, 
            allow_dangerous_deserialization=True
        )
        
    if _cross_encoder is None:
        # Initialize lightweight CPU-friendly cross-encoder model
        _cross_encoder = HuggingFaceCrossEncoder(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
        
    # Stage 1: Pull top 15 candidates based on broad bi-encoder similarity
    base_retriever = _vectorstore.as_retriever(search_kwargs={"k": 15})
    
    # Stage 2: Construct the contextual re-ranking pipeline
    return ContextualRerankingRetriever(
        base_retriever=base_retriever,
        cross_encoder=_cross_encoder,
        top_n=2
    )