import os
import re
import dotenv
import shutil
import time
import warnings
import asyncio
from pathlib import Path
from ingest import build_vector_db

# Suppress LlamaParse deprecation warning for clean terminal output
warnings.filterwarnings("ignore", category=DeprecationWarning)
from llama_parse import LlamaParse

# Initialize cloud keys
dotenv.load_dotenv()
os.environ["LLAMA_CLOUD_API_KEY"] = os.getenv("LLAMA_CLOUD_API_KEY")

def inject_metadata(raw_markdown: str, filename: str) -> str:
    """Injects the legal statute name into every Markdown Header."""
    clean_title = filename.replace("_", " ").replace("-", " ").upper()
    enhanced_markdown = re.sub(
        r'^(#+)\s*(.*)', 
        rf'\1 [{clean_title}] \2', 
        raw_markdown, 
        flags=re.MULTILINE
    )
    preamble = f"\n\n{'='*60}\n"
    preamble += f"# PRIMARY LEGAL STATUTE: {clean_title}\n"
    preamble += f"> SYSTEM DIRECTIVE: The following text is the authoritative legal language for the {clean_title}. "
    preamble += f"If you cite any clauses or sections below, you MUST attribute them to the {clean_title}.\n"
    preamble += f"{'='*60}\n\n"
    return preamble + enhanced_markdown

async def process_documents():
    curated_dir = Path("curated")
    scanned_dir = Path("scanned")
    master_output_path = "output.md"
    
    curated_dir.mkdir(exist_ok=True)
    scanned_dir.mkdir(exist_ok=True)
    
    # Ensure output.md exists to prevent FAISS crashes
    Path(master_output_path).touch(exist_ok=True)
    
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
        if not pdf_path.exists():
            continue
            
        print(f"Processing: {pdf_path.name}")
        start_time = time.perf_counter()
        
        try:
            # NATIVE ASYNC CALL (Bypasses all the event loop crashes)
            parsed_data = await parser.aload_data(str(pdf_path))
            raw_markdown = "\n\n".join([page.text for page in parsed_data])
            
            # The Safety Check that just saved your database!
            if len(raw_markdown.strip()) < 50:
                raise ValueError("LlamaParse returned empty or near-empty text. Skipping.")
            
            enriched_markdown = inject_metadata(raw_markdown, pdf_path.stem)
            
            with open(master_output_path, "a", encoding="utf-8") as master_file:
                master_file.write(enriched_markdown)
                master_file.write("\n\n")
                
            latency = time.perf_counter() - start_time
            print(f"Successfully compiled and injected metadata for {pdf_path.name} in {latency:.2f}s.")
            
            timestamp = int(time.time())
            archive_filename = f"{pdf_path.stem}_{timestamp}{pdf_path.suffix}"
            archive_destination = scanned_dir / archive_filename
            shutil.move(str(pdf_path), str(archive_destination))
            
        except Exception as e:
            print(f"Pipeline Execution Failure processing document '{pdf_path.name}': {str(e)}")

    print("--------------------------------------------------")
    print("Extraction complete. Initiating Vector Database Update...")
    try:
        build_vector_db() 
    except Exception as e:
        print(f"CRITICAL FAILURE: Could not update FAISS database. Error: {str(e)}")

if __name__ == "__main__":
    # Boot up the Native Python Async Event Loop
    asyncio.run(process_documents())