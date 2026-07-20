# temp_seed_pinecone.py
import os
from dotenv import load_dotenv

# 1. LOAD DOTENV FIRST
load_dotenv() 

# 2. THEN IMPORT YOUR MODULES
import json
from src.tools.gold_store import save_successful_audit

def run_seeder():
    json_path = "data/audit_responses.json"
    if not os.path.exists(json_path):
        print(f"❌ Error: {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"🚀 Found {len(data)} items. Starting Cloud Seeding...")

    for item in data:
        # Construct the content for the vault
        save_successful_audit(
            question=item['query'], 
            audit_report=item['expert_audit_response']
        )

if __name__ == "__main__":
    run_seeder()