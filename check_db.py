import os
from pinecone import Pinecone
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from dotenv import load_dotenv
load_dotenv()

_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def peek_inside(db_path, label):
    print(f"\n--- Checking {label} at {db_path} ---")
    if not os.path.exists(db_path):
        print(f"❌ DATABASE NOT FOUND.")
        return

    try:
        db = FAISS.load_local(db_path, _embeddings, allow_dangerous_deserialization=True)
        # Get all IDs in the index
        num_docs = db.index.ntotal
        print(f"✅ Status: Active")
        print(f"📊 Number of items stored: {num_docs}")
        
        # Pull one sample
        if num_docs > 0:
            # We do a dummy search to get some content
            docs = db.similarity_search(" ", k=1)
            print(f"📝 Sample Content: {docs[0].page_content[:100]}...")
    except Exception as e:
        print(f"⚠️ Error loading DB: {e}")

def check_cloud_vault():
    api_key = os.getenv("PINECONE_API_KEY")
    index_name = "clause-n-effect-vault"
    
    if not api_key:
        print("❌ PINECONE_API_KEY not found.")
        return

    pc = Pinecone(api_key=api_key)
    try:
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        print(f"\n--- Checking CLOUD GOLD VAULT (Pinecone) ---")
        print(f"✅ Status: Connected")
        print(f"📊 Total Expert Audits Stored: {stats['total_vector_count']}")
        print(f"🌲 Index Dimension: {stats['dimension']}")
    except Exception as e:
        print(f"❌ Could not connect to Pinecone: {e}")

if __name__ == "__main__":
    # Keep your FAISS check logic here too if you want
    check_cloud_vault()

    # Check both
    peek_inside("faiss_legal_db", "LEGAL LIBRARY (Statutes)")
    peek_inside("faiss_gold_vault", "GOLD VAULT (AI Success Memory)")
