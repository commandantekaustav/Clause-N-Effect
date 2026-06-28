import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# Process-level caching to prevent redundant I/O and memory overhead
_embeddings = None
_vectorstore = None

def get_retriever():
    """
    Loads and caches the local FAISS vector store. 
    Implements a safe fallback if the vector database files have not been compiled yet.
    """
    global _embeddings, _vectorstore
    
    if _embeddings is None:
        # Load lightweight MiniLM sentence-transformer model
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
    if _vectorstore is None:
        db_path = "faiss_legal_db"
        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"FAISS database directory '{db_path}' not found at the root level. "
                "Ensure that 'build_vector_db.py' or 'parser.py' has executed successfully."
            )
        _vectorstore = FAISS.load_local(
            db_path, 
            _embeddings, 
            allow_dangerous_deserialization=True
        )
        
    return _vectorstore.as_retriever(search_kwargs={"k": 3})