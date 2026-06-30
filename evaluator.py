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
    """Uses the 8B model to preserve our 70B daily token limit."""
    return ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.0, 
        max_tokens=500
    )

# Using JsonOutputParser bypasses Groq's flaky tool-calling API
parser = JsonOutputParser(pydantic_object=EvaluationScore)

EVALUATOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an impartial Supreme Court Judge evaluating an AI Compliance Auditor. "
               "Compare the 'AI Generated Audit' against the 'Expert Ground Truth'. "
               "Score the AI from 1 (completely wrong/hallucinated) to 5 (perfectly accurate, nuanced, and covers the ground truth). "
               "Also verify if the AI successfully cited the 'Target Statute'. "
               "Be strict. If the AI hallucinates non-existent laws, give it a 1.\n\n"
               "CRITICAL: {format_instructions}"),
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
            error_msg = str(e)
            
            # Catch standard network connection drops
            if "Connection error" in error_msg or "timeout" in error_msg.lower() or "503" in error_msg:
                print(f"\n[!] Network/Server glitch detected. Retrying in 10 seconds...")
                time.sleep(10)
                retries += 1
                continue
            
            # Detect Rate Limit Failures
            if "rate_limit_exceeded" in error_msg or "429" in error_msg:
                
                # Condition A: Tokens Per Day (TPD) Exhaustion
                if "tokens per day" in error_msg or "TPD" in error_msg:
                    if fallback_keys and current_key_idx < len(fallback_keys):
                        print(f"\n[!] Daily Limit Reached. Rotating to Fallback API Key {current_key_idx + 1}...")
                        os.environ["GROQ_API_KEY"] = fallback_keys[current_key_idx]
                        current_key_idx += 1
                        continue 
                    else:
                        print("\n[CRITICAL] Daily Token Limit (TPD) exhausted. No fallback keys available.")
                        raise Exception("TPD_EXHAUSTED")

                # Condition B: Tokens Per Minute (TPM) Exhaustion
                match = re.search(r'try again in (?:(\d+)m)?(?:([\d.]+)s)?', error_msg)
                if match:
                    minutes = int(match.group(1)) if match.group(1) else 0
                    seconds = float(match.group(2)) if match.group(2) else 0
                    wait_time = (minutes * 60) + seconds + 3.0 
                    print(f"\n[!] Rate Limit (TPM) Hit. Adaptive pause: Sleeping for {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                    retries += 1
                    continue
                else:
                    wait_time = 60 * (retries + 1)
                    print(f"\n[!] Rate Limit Hit (Unknown duration). Static pause: Sleeping for {wait_time} seconds...")
                    time.sleep(wait_time)
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
    evaluator_chain = EVALUATOR_PROMPT | get_evaluator_llm() | parser
    
    try:
        for i in range(start_index, len(dataset)):
            item = dataset[i]
            query = item.get("query", "")
            expert_answer = item.get("expert_audit_response", "")
            target_statute = item.get("primary_statute", "")
            
            print(f"Running Test {i+1}/{len(dataset)}: {item.get('category', 'General')}")
            
            # 1. Run the CRAG pipeline
            inputs = {"question": query, "revision_count": 0}
            try:
                graph_result = robust_invoke(crag_app, inputs)
                final_audit = graph_result.get("generation", "FAILED TO GENERATE")
            except Exception as e:
                if str(e) == "TPD_EXHAUSTED":
                    print("Benchmark aborted to prevent state corruption.")
                    break
                print(f"  -> CRAG Pipeline Failed: {e}")
                final_audit = "ERROR"
                
            # 2. Evaluate the Output
            try:
                if final_audit != "ERROR":
                    eval_result = robust_invoke(evaluator_chain, {
                        "statute": target_statute,
                        "expert": expert_answer,
                        "generated": final_audit,
                        "format_instructions": parser.get_format_instructions()
                    })
                    score = eval_result.get("accuracy_score", 0)
                    statute_match = eval_result.get("statute_match", False)
                    reasoning = eval_result.get("reasoning", "No reasoning provided.")
                else:
                    raise Exception("Skipping evaluation due to generation failure.")
            except Exception as e:
                if str(e) == "TPD_EXHAUSTED":
                    break
                print(f"  -> Evaluation Failed: {e}")
                score = 0
                statute_match = False
                reasoning = "Evaluation failed or was skipped."
            
            # 3. Save the record
            record = {
                "id": item.get("id", i),
                "query": query,
                "crag_output": final_audit,
                "expert_ground_truth": expert_answer,
                "accuracy_score": score,
                "statute_match": statute_match,
                "evaluator_reasoning": reasoning
            }
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