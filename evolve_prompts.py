import json
import os
import re
from langchain_groq import ChatGroq
from dotenv import load_dotenv

# 1. LOAD DOTENV AT THE VERY START
load_dotenv()

def evolve_system():
    # --- CHECK API KEY FIRST ---
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("❌ CRITICAL ERROR: GROQ_API_KEY not found in environment.")
        print("Ensure your .env file exists and contains GROQ_API_KEY=your_key")
        return

    log_path = ".DONT_UPLOAD/track.json"
    if not os.path.exists(log_path):
        print("❌ No logs found to evolve from.")
        return

    with open(log_path, "r") as f:
        try:
            logs = json.load(f)
        except Exception as e:
            print(f"❌ Failed to parse log file: {e}")
            return

    # 2. DEFENSIVE LOG FILTERING
    failures = []
    for entry in logs:
        if not isinstance(entry, dict): continue
        
        # Use .get() recursion to prevent KeyError
        metrics = entry.get("system_metrics", {})
        revisions = metrics.get("actor_critic_revisions", 0)
        
        # If the run needed multiple tries, it's a candidate for learning
        if revisions > 1:
            failures.append(entry)
    
    if not failures:
        print("✅ System is performing optimally. No revision friction detected.")
        return

    print(f"🧠 Analyzing {len(failures)} friction points to evolve logic...")

    # 3. INITIALIZE LLM SAFELY
    try:
        optimizer_llm = ChatGroq(
            model="llama-3.3-70b-versatile", 
            temperature=0.1,
            api_key=api_key # Explicitly pass the key
        )
    except Exception as e:
        print(f"❌ LLM Initialization failed: {e}")
        return
    
    # Take last 5 for context window management
    evolution_query = f"""
    You are a Meta-Prompt Optimizer. Analyze these failure logs:
    {json.dumps(failures[-5:], indent=2)}
    
    Identify which component caused the loop: GRADER, DEFENSE, AUDIT, or JUDGE.
    Return ONLY a JSON object with a 1-sentence 'PATCH' for the failing component(s).
    
    Example Output:
    {{
        "GRADER_PATCH": "",
        "DEFENSE_PATCH": "Make HR more aggressive about academic semesters.",
        "AUDIT_PATCH": "Directive: Citing Specific Relief Act is mandatory for resignation denial.",
        "JUDGE_PATCH": ""
    }}
    """
    
    try:
        response = optimizer_llm.invoke(evolution_query)
        
        # Regex to extract JSON block safely
        match = re.search(r"\{.*\}", str(response.content), re.DOTALL)
        if not match: 
            print("❌ Optimizer did not return valid JSON.")
            return
        
        new_patches = json.loads(match.group())
        
        # 4. APPLY THE PATCHES
        config_path = "src/prompts/dynamic_config.json"
        current_config = {"GRADER_PATCH": "", "DEFENSE_PATCH": "", "AUDIT_PATCH": "", "JUDGE_PATCH": ""}
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                try:
                    current_config.update(json.load(f))
                except: pass
        
        # Merge logic
        for key in current_config:
            if key in new_patches and new_patches[key]:
                current_config[key] = new_patches[key] 

        with open(config_path, "w") as f:
            json.dump(current_config, f, indent=2)
            
        print("🚀 System evolved. Patches applied to dynamic_config.json")

    except Exception as e:
        print(f"❌ Evolution failed: {e}")

if __name__ == "__main__":
    evolve_system()