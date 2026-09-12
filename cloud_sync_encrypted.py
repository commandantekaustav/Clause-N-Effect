# cloud_sync_encrypted.py
import os
import json
from dotenv import load_dotenv
load_dotenv()

from src.tools.gold_store import save_successful_audit, get_vault_index

def final_sync():
    print("🧹 Wiping unencrypted data from Pinecone...")
    try:
        index = get_vault_index()
        index.delete(delete_all=True)
    except: pass

    with open("data/audit_responses.json", "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"🔐 Seeding {len(dataset)} items with AES-128 Encryption...")
    for item in dataset:
        # Combine response and statute for a complete reference
        combined_audit = f"{item['expert_audit_response']}\nSTATUTE: {item['primary_statute']}"
        save_successful_audit(item['query'], combined_audit)
        print(f"✅ Encrypted & Synced: {item['category']}")

if __name__ == "__main__":
    final_sync()