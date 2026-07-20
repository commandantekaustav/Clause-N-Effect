import time
import streamlit as st

def execute_and_stream_graph(
    crag_app, 
    inputs: dict, 
    terminal_box, 
    input_tokens: int, 
    update_tracker_callback
):
    """
    Controller function to handle LangGraph streaming, token calculation,
    and UI updates (including full text expanders and the terminal log).
    """
    terminal_text = "> INITIALIZING CLAUSE-N-EFFECT PROTOCOL...\n"
    
    final_generation = ""
    final_steps = []
    distilled_query = inputs.get("question", "")
    final_revisions = 0
    final_rejection_reasons = []

    start_time = time.perf_counter()
    
    for output in crag_app.stream(inputs):
        for node_name, state_delta in output.items():
            
            # 1. Update Token Usage
            if node_name == "generate_audit":
                estimated_cost = input_tokens + 4000
            elif node_name == "grade_documents":
                estimated_cost = input_tokens + 2500
            elif node_name == "evaluate_audit":
                estimated_cost = input_tokens + 1500
            else:
                estimated_cost = input_tokens + 500
                
            st.session_state.session_tokens += estimated_cost
            update_tracker_callback()
            
            # ---------------------------------------------------------
            # 2. RESTORE FULL UI VISIBILITY FOR INTERMEDIATE GENERATIONS
            # ---------------------------------------------------------
            if "corporate_defense" in state_delta and state_delta["corporate_defense"]:
                with st.expander("🛡️ Corporate HR Defense Generated (Red Team)", expanded=False):
                    st.write(state_delta["corporate_defense"])
                    
            if "judge_feedback" in state_delta and state_delta.get("judge_score") == "FAIL":
                st.warning(f"⚠️ Judge Rejected Audit. Triggering Rewrite. Reason: {state_delta['judge_feedback']}")
            # ---------------------------------------------------------

            # 3. Build the Sci-Fi Thought Stream (For the terminal box)
            terminal_text += f"\n> [SYSTEM EVENT] NODE: {node_name.upper()}"
            
            if node_name == "compress_query" and "question" in state_delta:
                snippet = state_delta["question"][:90].replace("\n", " ") + "..."
                terminal_text += f"\n  -> Distilling Facts: '{snippet}'"
                
            elif node_name == "retrieve":
                terminal_text += f"\n  -> Extracted {len(state_delta.get('documents', []))} relevant statutory sections."
                
            elif node_name == "grade_documents" and "generation" in state_delta:
                terminal_text += f"\n  -> Document Relevance Check: {state_delta['generation']}"
                
            elif node_name == "web_search" and "web_search_context" in state_delta:
                terminal_text += f"\n  -> Activating Corrective Web Search for latest statutes..."
                
            elif node_name == "draft_corporate_defense":
                terminal_text += f"\n  -> Red Teaming (Drafting HR Defense)..."
                
            elif node_name == "generate_audit":
                terminal_text += f"\n  -> Compiling Final Statutory Audit..."
                
            elif node_name == "evaluate_audit":
                score = state_delta.get('judge_score')
                terminal_text += f"\n  -> Critic Evaluation: {score}"
                if score == "FAIL":
                    terminal_text += f"\n> [SYSTEM EVENT] INITIATING SELF-CORRECTION REWRITE..."
            
            # Render the text inside the terminal container
            terminal_box.markdown(f"```text\n{terminal_text}\n```")
            time.sleep(0.4) # Typewriter effect pause
            
            # 4. Capture Final State
            if "steps" in state_delta:
                final_steps = state_delta["steps"]
            if "generation" in state_delta:
                final_generation = state_delta["generation"]
            if "question" in state_delta:
                distilled_query = state_delta["question"]
            if "revision_count" in state_delta:
                final_revisions = state_delta["revision_count"]
            if "rejection_reasons" in state_delta:
                final_rejection_reasons = state_delta["rejection_reasons"]

    execution_latency = time.perf_counter() - start_time

    raw_query = inputs.get("question", "")
    parts = raw_query.split("TARGET HR FACTS:")
    user_query_only = parts[0].replace("USER QUERY:", "").strip() if len(parts) > 0 else raw_query
    hr_facts_only = parts[1].strip() if len(parts) > 1 else "No HR Facts provided."
    
    # Add final_rejection_reasons to the return statement
    return final_generation, final_steps, user_query_only, hr_facts_only, final_revisions, final_rejection_reasons, execution_latency