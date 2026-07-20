import os
import json
from dotenv import load_dotenv
load_dotenv()

from src.tools.gold_store import save_successful_audit, get_vault_index

def sync_everything():
    # 1. Clear the current cloud index to ensure a clean slate
    print("🧹 Cleaning Cloud Vault...")
    try:
        index = get_vault_index()
        index.delete(delete_all=True)
        print("✅ Cloud Vault Wiped.")
    except Exception as e:
        print(f"⚠️ Clean failed (might be empty): {e}")

    # 2. Load the full Golden Dataset (the 20 items we refined)
    json_path = "data/audit_responses.json"
    with open(json_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"🚀 Syncing {len(dataset)} Expert Audits to Pinecone...")
    
    for item in dataset:
        # Push to Pinecone
        save_successful_audit(
            question=item['query'], 
            audit_report=f"{item['expert_audit_response']}\nPRIMARY STATUTE: {item['primary_statute']}"
        )
        print(f"✅ Synced: {item['category']}")

    print("\n✨ SYNCHRONIZATION COMPLETE. Cloud Vault is now at full strength.")

if __name__ == "__main__":
    sync_everything()