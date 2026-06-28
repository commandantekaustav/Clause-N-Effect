import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import MarkdownTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def build_vector_db():
    print("1. Loading output.md...")
    loader = TextLoader("output.md", encoding="utf-8")
    documents = loader.load()

    print("2. Chunking Markdown...")
    # MarkdownTextSplitter respects headers and markdown syntax
    text_splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    print(f"   Created {len(chunks)} chunks.")

    print("3. Initializing Embedding Model (Downloading model if first run)...")
    # This runs locally and for free
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print("4. Building FAISS Index...")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    print("5. Saving to disk...")
    vectorstore.save_local("faiss_legal_db")
    print("✅ Vector database built and saved to the 'faiss_legal_db' directory!")

if __name__ == "__main__":
    build_vector_db()