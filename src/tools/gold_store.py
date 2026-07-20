import os
import time
from src.utils.security import encrypt_text, decrypt_text

from pinecone import Pinecone, ServerlessSpec
from langchain_huggingface import HuggingFaceEmbeddings

# Credentials
try:
    PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
    INDEX_NAME = "clause-n-effect-vault"
except Exception as e:
    print(f"Error occurred while fetching environment variables: {e}")

# Initialize Embeddings
_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def get_vault_index():
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY not found in environment variables.")
    
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    # Check if index exists
    existing_indexes = [index.name for index in pc.list_indexes()]
    if INDEX_NAME not in existing_indexes:
        print(f"Creating Cloud Vault: {INDEX_NAME}...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384, # Matches all-MiniLM-L6-v2
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        # Wait for index to be ready
        while not pc.describe_index(INDEX_NAME).status['ready']:
            time.sleep(1)
            
    return pc.Index(INDEX_NAME)

def save_successful_audit(question: str, audit_report: str):
    try:
        index = get_vault_index()
        vector = _embeddings.embed_query(question)
        import hashlib
        doc_id = hashlib.md5(question.encode()).hexdigest()
        
        # ENCRYPT the audit before saving
        encrypted_audit = encrypt_text(audit_report)
        
        index.upsert(vectors=[{
            "id": doc_id,
            "values": vector,
            "metadata": {
                "question": question, # We leave the question as is for similarity
                "audit": encrypted_audit 
            }
        }])
    except Exception as e:
        print(f"Cloud Save Failed: {e}")

def get_similar_success(question: str) -> str:
    try:
        index = get_vault_index()
        vector = _embeddings.embed_query(question)
        results = index.query(vector=vector, top_k=1, include_metadata=True)
        
        if not results['matches']: return "No prior examples."
        
        match = results['matches'][0]
        past_q = match['metadata']['question']
        # DECRYPT after fetching
        past_audit = decrypt_text(match['metadata']['audit'])
        
        return f"--- GOLD STANDARD REFERENCE ---\nQUERY: {past_q}\nAUDIT:\n{past_audit}"
    except Exception:
        return "Memory Offline."