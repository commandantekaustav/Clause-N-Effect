import os
import dotenv
import shutil
import time
import warnings
from pathlib import Path
from ingest import build_vector_db

# Suppress LlamaParse deprecation warning for clean terminal output
warnings.filterwarnings("ignore", category=DeprecationWarning)
from llama_parse import LlamaParse

# Initialize cloud keys
dotenv.load_dotenv()
os.environ["LLAMA_CLOUD_API_KEY"] = os.getenv("LLAMA_CLOUD_API_KEY")

def ingest_curated_documents(
    curated_dir_path: str = "curated", 
    scanned_dir_path: str = "scanned", 
    master_output_path: str = "output.md"
):
    """
    Automated batch processing pipeline. Parses PDFs in the curated directory,
    appends markdown output, and safely moves processed documents to scanned archive.
    """
    curated_dir = Path(curated_dir_path)
    scanned_dir = Path(scanned_dir_path)
    
    # Ensure execution directories exist
    curated_dir.mkdir(exist_ok=True)
    scanned_dir.mkdir(exist_ok=True)
    
    # THE FIX: Use a set() to eliminate duplicate files caused by Windows case-insensitivity
    raw_files = list(curated_dir.glob("*.pdf")) + list(curated_dir.glob("*.PDF"))
    pdf_files = list(set(raw_files))
    
    if not pdf_files:
        print(f"No documents detected in administrative directory: '{curated_dir.resolve()}'. Ingestion idle.")
        return

    print(f"Scanning detected {len(pdf_files)} unique target document(s). Initializing LlamaParse...")
    
    parser = LlamaParse(
        result_type="markdown",
        num_workers=4,
        verbose=True,
    )
    
    for pdf_path in pdf_files:
        # Failsafe: Ensure file hasn't been moved or deleted by another process
        if not pdf_path.exists():
            continue
            
        print(f"Processing: {pdf_path.name}")
        start_time = time.perf_counter()
        
        try:
            # Parse PDF through Cloud Engine
            parsed_data = parser.load_data(str(pdf_path))
            combined_markdown = "\n\n".join([page.text for page in parsed_data])
            
            # Append markdown payload to cumulative master record
            with open(master_output_path, "a", encoding="utf-8") as master_file:
                master_file.write(f"\n\n# Document Reference: {pdf_path.stem}\n")
                master_file.write(f"--- Ingestion Timestamp: {time.asctime()} ---\n\n")
                master_file.write(combined_markdown)
                master_file.write("\n\n")
                
            latency = time.perf_counter() - start_time
            print(f"Successfully compiled markdown for {pdf_path.name} in {latency:.2f}s.")
            
            # Build non-colliding destination path in archive directory
            timestamp = int(time.time())
            archive_filename = f"{pdf_path.stem}_{timestamp}{pdf_path.suffix}"
            archive_destination = scanned_dir / archive_filename
            
            # Relocate file to commit pipeline stage
            shutil.move(str(pdf_path), str(archive_destination))
            print(f"Moved source file to archive: '{archive_destination.name}'\n")
            
        except Exception as e:
            print(f"Pipeline Execution Failure processing document '{pdf_path.name}': {str(e)}")
            print("Document retained in curated execution path for recovery.\n")

 # ==========================================
    # THE PIPELINE TRIGGER (ADD THIS AT THE VERY END OF THE FUNCTION)
    # ==========================================
    print("--------------------------------------------------")
    print("Extraction complete. Initiating Vector Database Update...")
    try:
        build_vector_db() # This calls your ingest.py logic automatically
    except Exception as e:
        print(f"CRITICAL FAILURE: Could not update FAISS database. Error: {str(e)}")

if __name__ == "__main__":
    ingest_curated_documents()