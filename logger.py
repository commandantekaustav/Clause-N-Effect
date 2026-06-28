import os
import json
import time
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(".DONT_UPLOAD")
LOG_FILE = LOG_DIR / "track.json"

def log_transaction(query: str, response: str, steps: list, execution_time: float):
    """
    Automated logging framework for local evaluation and cost analysis.
    Stores logs in a structured JSON array for direct parsing into Pandas later.
    """
    LOG_DIR.mkdir(exist_ok=True)
    
    # Estimate token consumption roughly (1 word ≈ 1.33 tokens)
    estimated_tokens = int((len(query) + len(response)) / 4)
    
    new_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "performance": {
            "latency_seconds": round(execution_time, 2),
            "estimated_tokens": estimated_tokens
        },
        "routing": {
            "pipeline_path": steps,
            "web_search_triggered": "execute_web_search" in steps
        },
        "data": {
            "prompt": query.strip(),
            "response": response.strip()
        }
    }
    
    # Read existing logs or initialize an empty list
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > 0:
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except json.JSONDecodeError:
            logs = []
    else:
        logs = []
        
    # Append the new transactional log
    logs.append(new_entry)
    
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)

# --- Example Integration inside your execution block ---
# start_time = time.time()
# response = crag_app.invoke({"question": user_query})
# latency = time.time() - start_time
# log_transaction(user_query, response["generation"], response["steps"], latency)