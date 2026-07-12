"""
An utility module for structured telemetry logging of transactions. This module is designed to handle schema migrations dynamically, 
ensuring that historical evaluations remain intact while new entries are logged with enhanced metadata. 
It captures execution details, model configurations, and routing metrics in a structured JSON format for easy analysis and auditing.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from src.utils.pii_scrubber import scrub_pii

LOG_DIR = Path(".DONT_UPLOAD")
LOG_FILE = LOG_DIR / "track.json"

def log_transaction(
    query: str, 
    hr_facts: str, 
    response: str, 
    steps: list, 
    execution_time: float,
    revision_count: int = 0,
    rejection_reasons: list = None
    ):
    """
    Structured telemetry logging agent. Handles schema migrations dynamically
    without crashing historical evaluations.
    """
    if rejection_reasons is None:
        rejection_reasons = []
        
    LOG_DIR.mkdir(exist_ok=True)
    target_model = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    
    query_chars = len(query)
    response_chars = len(response)
    estimated_tokens = int((query_chars + response_chars) / 4)
    
    # --- PII SCRUBBING PHASE ---
    safe_query = scrub_pii(query.strip())
    safe_facts = scrub_pii(hr_facts.strip())

    # Upgraded schema with consolidated metrics
    new_entry = {
        "execution_number": None, 
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system_metrics": {
            "model_identifier": target_model,
            "latency_seconds": round(execution_time, 4),
            "estimated_tokens": estimated_tokens,
            "actor_critic_revisions": revision_count,
            "judge_rejection_reasons": rejection_reasons, 
            "external_search_triggered": "execute_web_search" in steps
        },
        "routing_metrics": {
            "completed_graph_nodes": steps,
        },
        "transactional_payload": {
            "query_prompt": safe_query,
            "hr_facts": safe_facts,
            "response_analysis": response.strip()
        }
    }
    
    logs = []
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except json.JSONDecodeError:
            logs = []
            
    for index, entry in enumerate(logs):
        if not isinstance(entry, dict):
            continue
        if "execution_number" not in entry or entry["execution_number"] is None:
            entry["execution_number"] = index + 1
            
    new_entry["execution_number"] = len(logs) + 1
    logs.append(new_entry)
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)