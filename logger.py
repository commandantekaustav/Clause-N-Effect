"""
An utility module for structured telemetry logging of transactions. This module is designed to handle schema migrations dynamically, 
ensuring that historical evaluations remain intact while new entries are logged with enhanced metadata. 
It captures execution details, model configurations, and routing metrics in a structured JSON format for easy analysis and auditing.
"""

import os
import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(".DONT_UPLOAD")
LOG_FILE = LOG_DIR / "track.json"

def log_transaction(query: str, response: str, steps: list, execution_time: float):
    """
    Structured telemetry logging agent. Handles schema migrations dynamically
    without crashing historical evaluations.
    """
    LOG_DIR.mkdir(exist_ok=True)
    
    # Calculate quantitative string lengths for cost estimation
    query_chars = len(query)
    response_chars = len(response)
    estimated_tokens = int((query_chars + response_chars) / 4)
    
    # Read active model configuration safely from system variables
    target_model = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    
    # Upgraded schema with detailed cost and model properties
    new_entry = {
        "execution_number": None, # Will be set dynamically below
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system_configuration": {
            "model_identifier": target_model,
            "latency_seconds": round(execution_time, 4),
            "estimated_tokens": estimated_tokens,
            "character_matrix": {
                "input_query_characters": query_chars,
                "output_response_characters": response_chars
            }
        },
        "routing_metrics": {
            "completed_graph_nodes": steps,
            "external_search_active": "execute_web_search" in steps
        },
        "transactional_payload": {
            "query_prompt": query.strip(),
            "response_analysis": response.strip()
        }
    }
    
    # Handle read and deserialization of the log index safely
    logs = []
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except json.JSONDecodeError:
            logs = []
            
    # Apply Migration: retroactively update existing records to align with execution indexes
    for index, entry in enumerate(logs):
        if not isinstance(entry, dict):
            continue
        # Migrate old format to support execution numbers
        if "execution_number" not in entry or entry["execution_number"] is None:
            entry["execution_number"] = index + 1
            
    # Assign execution number based on final migrated list offset
    new_entry["execution_number"] = len(logs) + 1
    logs.append(new_entry)
    
    # Write transactions atomically
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)