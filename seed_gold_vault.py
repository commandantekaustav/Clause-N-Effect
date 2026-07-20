# seed_gold_vault.py (Corrected Version)
import json
import os
from src.tools.gold_store import save_successful_audit

def seed_vault():
    json_path = "data/audit_responses.json"
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for entry in data:
        # We pass both the response and statute to the save function
        combined_expert = f"{entry['expert_audit_response']}\nPRIMARY STATUTE: {entry['primary_statute']}"
        save_successful_audit(
            question=entry["query"], 
            audit_report=combined_expert
        )
        print(f"✅ Seeded: {entry['category']}")

if __name__ == "__main__":
    # DELETE OLD FOLDER FIRST
    import shutil
    if os.path.exists("faiss_gold_vault"):
        shutil.rmtree("faiss_gold_vault")
    seed_vault()