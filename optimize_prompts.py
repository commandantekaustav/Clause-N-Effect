import json
import os
from collections import Counter

# Path to your telemetry log
LOG_PATH = ".DONT_UPLOAD/track.json"

def analyze_failures():
    if not os.path.exists(LOG_PATH):
        print(f"Error: {LOG_PATH} not found. Run a few audits first!")
        return

    try:
        with open(LOG_PATH, "r") as f:
            # Handle cases where file is a list of JSON objects
            data = json.load(f)
            # Ensure data is a list
            logs = data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"Error reading logs: {e}")
        return

    total_runs = len(logs)
    failed_evaluations = []
    all_rejection_reasons = []

    for entry in logs:
        # Check system_metrics for revisions (Actor-Critic activity)
        metrics = entry.get("system_metrics", {})
        revisions = metrics.get("actor_critic_revisions", 0)
        rejection_reasons = metrics.get("judge_rejection_reasons", [])

        if revisions > 0 or rejection_reasons:
            failed_evaluations.append(entry)
            all_rejection_reasons.extend(rejection_reasons)

    # --- THE REPORT ---
    print("="*50)
    print("CLAUSE-N-EFFECT: SELF-CORRECTION ANALYSIS")
    print("="*50)
    print(f"Total Audits Logged: {total_runs}")
    print(f"Audits Requiring Correction: {len(failed_evaluations)}")
    
    if total_runs > 0:
        failure_rate = (len(failed_evaluations) / total_runs) * 100
        print(f"Self-Correction Rate: {failure_rate:.2f}%")

    if all_rejection_reasons:
        print("\n--- TOP JUDGE REJECTIONS ---")
        reason_counts = Counter(all_rejection_reasons)
        for reason, count in reason_counts.most_common(5):
            print(f"[{count} times]: {reason}")

    print("\n--- OPTIMIZATION BRIEF FOR LLM ---")
    print("Copy the text below and feed it to Llama-3.3-70B to improve your System Prompt:\n")
    
    brief = {
        "context": "The following is a summary of failures from a Legal Audit AI system.",
        "failure_samples": [
            {
                "query": log["transactional_payload"]["query_prompt"][:100] + "...",
                "rejections": log["system_metrics"]["judge_rejection_reasons"]
            } for log in failed_evaluations[-3:] # Last 3 failures
        ]
    }
    print(json.dumps(brief, indent=2))
    print("\n" + "="*50)

if __name__ == "__main__":
    analyze_failures()