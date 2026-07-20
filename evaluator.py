import os
import re
import sys
import json
import time
from typing import List
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.agents.graph import app as crag_app

class EvaluationScore(BaseModel):
    """Schema for the LLM-as-a-Judge to grade the CRAG system's output."""
    accuracy_score: int = Field(description="Score from 1 to 5 representing legal accuracy and alignment with ground truth.")
    statute_match: bool = Field(description="True if the CRAG output cited the correct primary statute, False otherwise.")
    reasoning: str = Field(description="One sentence explaining the score.")

def get_evaluator_llm():
    """Uses the 8B model with Native JSON Mode for absolute stability."""
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.0, 
        max_tokens=500,
        # This tells the Groq API to force a raw JSON string response
        model_kwargs={"response_format": {"type": "json_object"}} 
    )

# Notice we explicitly tell it the exact JSON keys we want
EVALUATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an impartial, ruthless Supreme Court Judge evaluating an AI Compliance Auditor. 
Your primary duty is to protect the end-user from false legal confidence. 
Compare the 'AI Generated Audit' against the 'Expert Ground Truth'.

SCORING RUBRIC (1 to 5):
5: PERFECT. The AI cited the EXACT Indian Act and the EXACT Section/Rule number. The legal reasoning is flawless.
4: ALMOST PERFECT. The AI cited the correct Indian Act, but missed the specific Section number or lacked slight nuance.
3: DANGEROUSLY VAGUE. The AI got the general sentiment right, but failed to cite a specific Act or relied entirely on generic principles.
2: MATERIALLY FLAWED. The AI cited the WRONG Indian Act (e.g., citing the IT Act instead of the DPDP Act).
1: CATASTROPHIC FAILURE. The AI hallucinated non-existent laws, cited foreign laws (e.g., US HIPAA, ADA, GDPR), or gave advice that would legally harm the user.

STATUTE MATCH LOGIC: 
- If the Expert Ground Truth cites 'Section 27 of the Contract Act' and the AI cites 'Industrial Disputes Act', this is a MATERIALLY FLAWED (2/5) score.
- Do NOT give points for 'General Principles'. We need Statues.
- If the user is Male and the AI mentions 'POSH', automatically give an ACCURACY_SCORE of 1.
You must output 'True' for `statute_match` ONLY IF the AI cited the actual, legally equivalent statute as the Target Statute. 
STATUTE MATCH LOGIC: Output 'True' if the AI identifies the correct core Indian Act. It does not need the exact year or full formal title, as long as the legal mechanism matches the Ground Truth perfectly. Do not pass incorrect laws.     
OUTPUT FORMAT:
You MUST return a valid JSON object with exactly these three keys:
"accuracy_score": (integer 1-5)
"statute_match": (boolean true/false)
"reasoning": (string)"""),
    ("human", "Target Statute: {statute}\n\nExpert Ground Truth: {expert}\n\nAI Generated Audit:\n{generated}")
])



def robust_invoke(chain_or_app, inputs: dict, max_retries: int = 4):
    """
    Advanced execution wrapper that intercepts 429 Rate Limits and Network Drops.
    """
    retries = 0
    fallback_keys = os.environ.get("GROQ_FALLBACK_KEYS", "").split(",")
    fallback_keys = [k.strip() for k in fallback_keys if k.strip()]
    current_key_idx = 0

    while retries < max_retries:
        try:
            return chain_or_app.invoke(inputs)
        except Exception as e:
            error_msg = str(e).lower()
            
            if "connection error" in error_msg or "timeout" in error_msg or "503" in error_msg:
                print(f"\n[!] Network glitch. Retrying in 10s...")
                time.sleep(10)
                retries += 1
                continue
            
            if "rate_limit" in error_msg or "429" in error_msg or "tpd" in error_msg:
                if fallback_keys and current_key_idx < len(fallback_keys):
                    next_key = fallback_keys[current_key_idx]
                    print(f"\n[!] Limit Reached. Swapping to Fallback Key {current_key_idx + 1}...")
                    
                    # THE MULTI-PROVIDER HACK:
                    # If you put an OpenRouter key in your fallback list, we change the endpoint!
                    if next_key.startswith("sk-or-"): 
                        os.environ["GROQ_API_BASE"] = "https://openrouter.ai/api/v1"
                    
                    os.environ["GROQ_API_KEY"] = next_key
                    current_key_idx += 1
                    continue 
                
                # If no keys left, sleep for a flat 60 seconds instead of brittle regex parsing
                print(f"\n[!] TPM Hit. No fallbacks ready. Sleeping 65 seconds...")
                time.sleep(65)
                retries += 1
                continue
            else:
                raise e
                
    raise Exception("Max retries exceeded due to persistent errors.")

def run_benchmark(dataset_path: str = "./data/audit_responses.json", output_path: str = ".DONT_UPLOAD/benchmark_results.json"):
    """Executes the benchmark suite across the Golden Dataset with fault tolerance."""
    
    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        try:
            dataset = json.load(f)
        except json.JSONDecodeError:
            print("Invalid JSON in dataset.")
            return

    if isinstance(dataset, dict):
        dataset = [dataset]

    results = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
            print(f"Loaded {len(results)} previous benchmark results. Resuming...")
        except json.JSONDecodeError:
            pass

    start_index = len(results)

    if start_index >= len(dataset):
        print("Benchmark already fully completed!")
        return
        
    print(f"Starting Benchmark across {len(dataset)} queries...\n")
    print("Press Ctrl+C at any time to gracefully pause and save current progress.\n")
    
    # Define evaluator chain using the raw JSON parser
    evaluator_chain = EVALUATOR_PROMPT | get_evaluator_llm()
    
    try:
        for i in range(start_index, len(dataset)):
            item = dataset[i]
            query = item.get("query", "")
            expert_answer = item.get("expert_audit_response", "")
            target_statute = item.get("primary_statute", "")
            
            print(f"Running Test {i+1}/{len(dataset)}: {item.get('category', 'General')}")
            
            # 1. Run the CRAG pipeline
            inputs = {
                "question": query, 
                "revision_count": 0,
                "gender": "male", # Crucial for your statutory routing
                "work_state": "Karnataka",
                "is_manager": False,
                "rejection_reasons": []
            }

            final_audit = "ERROR"
            revisions = 0 # Initialize here to prevent UnboundLocalError

            try:
                graph_result = robust_invoke(crag_app, inputs)
                final_audit = graph_result.get("generation", "FAILED TO GENERATE")
                revisions = graph_result.get("revision_count", 0)
            except Exception as e:
                print(f"  -> CRAG Pipeline Failed: {e}")
                
            # 2. Evaluate the Output
            score = 0
            statute_match = False
            reasoning = "Evaluation skipped due to failure."

            if final_audit != "ERROR":
                try:
                    time.sleep(2) 
                    eval_result_raw = robust_invoke(evaluator_chain, {
                        "statute": target_statute,
                        "expert": expert_answer,
                        "generated": final_audit
                    })
                    eval_dict = json.loads(eval_result_raw.content)
                    score = int(eval_dict.get("accuracy_score", 0))
                    statute_match = str(eval_dict.get("statute_match", "false")).lower() == "true"
                    reasoning = eval_dict.get("reasoning", "No reasoning.")
                except Exception as e:
                    print(f"  -> Evaluation Failed: {e}")

            # 3. Save the record (Now safe from UnboundLocalError)
            record = {
                "id": item.get("id", i),
                "query": query,
                "revisions_needed": revisions, 
                "crag_output": final_audit,
                "expert_ground_truth": expert_answer,
                "accuracy_score": score,
                "statute_match": statute_match,
                "evaluator_reasoning": reasoning
            }
            # ... rest of save logic
            results.append(record)
            
            print(f"  -> Score: {score}/5 | Statute Matched: {statute_match}")
            print(f"  -> Reasoning: {reasoning}\n")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            time.sleep(4) 
            
    except KeyboardInterrupt:
        print("\n[!] KeyboardInterrupt detected. Gracefully pausing benchmark and flushing data to disk...")

    # Calculate Analytics
    avg_score = sum(r.get("accuracy_score", 0) for r in results) / len(results) if results else 0
    statute_success_rate = (sum(1 for r in results if r.get("statute_match", False)) / len(results)) * 100 if results else 0
    
    print("="*40)
    print(f"BENCHMARK SESSION HALTED")
    print(f"Completed: {len(results)}/{len(dataset)}")
    print(f"Average Accuracy: {avg_score:.2f} / 5.0")
    print(f"Statute Retrieval Success: {statute_success_rate:.1f}%")
    print("="*40)
    print(f"Detailed report saved to {output_path}")

if __name__ == "__main__":
    if not os.environ.get("GROQ_API_KEY"):
        os.environ["GROQ_API_KEY"] = input("Enter Primary Groq API Key: ")
        
    if not os.environ.get("GROQ_FALLBACK_KEYS"):
        fallback_input = input("Enter Fallback Groq Keys (comma-separated, or press Enter to skip): ")
        if fallback_input.strip():
            os.environ["GROQ_FALLBACK_KEYS"] = fallback_input
            
    if not os.environ.get("TAVILY_API_KEY"):
        os.environ["TAVILY_API_KEY"] = input("Enter Tavily API Key: ")
        
    run_benchmark()