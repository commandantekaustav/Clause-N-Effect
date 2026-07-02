import os
import time
import streamlit as st
from agent_engine import app as crag_app
from logger import log_transaction

import dotenv
dotenv.load_dotenv()

st.set_page_config(
    page_title="FACEPREP CAPSTONE AGENT",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State for Token Tracking
if "session_tokens" not in st.session_state:
    st.session_state.session_tokens = 0
if "last_run_time" not in st.session_state:
    st.session_state.last_run_time = 0

GROQ_TPM_LIMIT = 6000  # Tokens Per Minute

st.title("Clause-N-Effect")
st.subheader("A legal sidekick for the gen-z workforce.")

with st.sidebar:
    st.header("Configuration")
    groq_api_key = st.text_input("Groq API Key", type="password")
    tavily_api_key = st.text_input("Tavily API Key", type="password")
    
    st.markdown("---")
    st.markdown("### API Usage Tracker")
    
    # 1. THE SLEDGEHAMMER: A single empty container we will completely overwrite
    sidebar_tracker = st.empty()
    
    def draw_sidebar_tracker():
        """Wipes and redraws the sidebar tracker live."""
        # Check if 60 seconds have passed since the last run to reset tokens
        if time.time() - st.session_state.last_run_time > 60:
            st.session_state.session_tokens = 0
            
        usage_percent = min(st.session_state.session_tokens / GROQ_TPM_LIMIT, 1.0)
        
        # Redraw everything inside the container
        with sidebar_tracker.container():
            st.progress(usage_percent)
            st.caption(f"**Groq TPM Usage (approx):** {int(st.session_state.session_tokens)} / {GROQ_TPM_LIMIT}")
            
            if usage_percent >= 1.0:
                st.error("❌ Rate Limit Hit (Wait 60s)")
            elif usage_percent > 0.8:
                st.warning("⚠️ Approaching Free Tier limit!")
            else:
                st.success("✅ API Status: Healthy")

    # Draw it immediately on load
    draw_sidebar_tracker()

    st.markdown("---")
    st.markdown("### Telemetry Status")
    if os.path.exists(".DONT_UPLOAD/track.json"):
        st.info("Telemetry Active: Logging to `.DONT_UPLOAD/track.json`")
    else:
        st.info("No logs captured yet.")

# ==========================================
# UI HELPER: 6-Slice Token Progress Bar
# ==========================================
def render_token_progress(text, max_tokens):
    words = len(text.split())
    tokens = int(len(text) / 4) # Standard 1 token ~= 4 chars approximation
    
    percentage = min(tokens / max_tokens, 1.0)
    filled = max(1, int(percentage * 6)) if tokens > 0 else 0
        
    colors = ["#4caf50", "#8bc34a", "#cddc39", "#ffeb3b", "#ff9800", "#f44336"]
    
    slices_html = ""
    for i in range(6):
        color = colors[i] if i < filled else "#e0e0e0" 
        margin = "4px" if i < 5 else "0px"
        slices_html += f'<div style="flex: 1; height: 8px; background-color: {color}; margin-right: {margin}; border-radius: 3px; transition: background-color 0.3s ease;"></div>'
        
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #888; margin-top: -12px; margin-bottom: 4px;">
        <span>Words: <b>{words}</b></span>
        <span>Tokens: <b>~{tokens}</b> / {max_tokens} (Optimal)</span>
    </div>
    <div style="display: flex; width: 100%; margin-bottom: 15px;">
        {slices_html}
    </div>
    """, unsafe_allow_html=True)
# ==========================================

col1, col2 = st.columns(2)

with col1:
    employer_facts = st.text_area(
        "1. Paste the Employer Clause / Email:",
        placeholder="Paste the HR email or contract clause here...",
        height=200,
    )
    render_token_progress(employer_facts, max_tokens=1500)

with col2:
    user_query = st.text_area(
        "2. What is your legal query?",
        placeholder="e.g., Is this legal? Am I obligated?",
        height=200
    )
    render_token_progress(user_query, max_tokens=300)

if st.button("Run Compliance Audit", type="primary"):
    if not groq_api_key or not tavily_api_key:
        st.error("Please provide both Groq and Tavily API keys in the sidebar.")
    elif not user_query.strip() or not employer_facts.strip():
        st.warning("Please fill out both the employer facts and your specific query.")
    else:
        # Pre-flight check: If they are already over the limit, block the execution
        # Make sure to update the sidebar so it actively shows the cooldown status
        draw_sidebar_tracker() 
        
        if st.session_state.session_tokens >= GROQ_TPM_LIMIT and (time.time() - st.session_state.last_run_time) < 60:
            st.error("Groq Free Tier Rate Limit reached. Please wait 60 seconds before running another audit.")
        else:
            os.environ["GROQ_API_KEY"] = groq_api_key
            os.environ["TAVILY_API_KEY"] = tavily_api_key
            
            input_tokens = int(len(employer_facts + user_query) / 4)
            status_placeholder = st.empty()
            
            combined_payload = f"USER QUERY: {user_query.strip()}\n\nTARGET HR FACTS:\n{employer_facts.strip()}"
            
            inputs = {
                "question": combined_payload,
                "revision_count": 0
            }
            
            final_generation = ""
            final_steps = []
            distilled_query = combined_payload 
            
            start_time = time.perf_counter()
            
            try:
                with status_placeholder.status("Executing Actor-Critic Routing Nodes...", expanded=True) as status:
                    for output in crag_app.stream(inputs):
                        for node_name, state_delta in output.items():
                            st.write(f"Completed Node: {node_name}")
                            
                            # --- REALISTIC TOKEN TRACKING ---
                            if node_name == "generate_audit":
                                estimated_cost = input_tokens + 4000
                            elif node_name == "grade_documents":
                                estimated_cost = input_tokens + 2500
                            elif node_name == "evaluate_audit":
                                estimated_cost = input_tokens + 1500
                            else:
                                estimated_cost = input_tokens + 500
                                
                            st.session_state.session_tokens += estimated_cost
                            
                            # LIVE UI UPDATE: Redraw the sidebar entirely
                            draw_sidebar_tracker()
                            # --------------------------------
                            
                            if "corporate_defense" in state_delta and state_delta["corporate_defense"]:
                                with st.expander("Corporate HR Defense Generated"):
                                    st.write(state_delta["corporate_defense"])
                                    
                            if "judge_feedback" in state_delta and state_delta.get("judge_score") == "FAIL":
                                st.warning(f"Judge Rejected Audit. Triggering Rewrite. Reason: {state_delta['judge_feedback']}")
                            
                            if "steps" in state_delta:
                                final_steps = state_delta["steps"]
                            if "generation" in state_delta:
                                final_generation = state_delta["generation"]
                            if "question" in state_delta:
                                distilled_query = state_delta["question"]
                    
                    status.update(label="Audit Completed!", state="complete", expanded=False)
                
                execution_latency = time.perf_counter() - start_time
                st.session_state.last_run_time = time.time()
                
                st.markdown(final_generation, unsafe_allow_html=True)
                
                log_transaction(
                    query=distilled_query,
                    response=final_generation,
                    steps=final_steps,
                    execution_time=execution_latency
                )
                
                st.toast(f"Audit completed in {execution_latency:.2f}s. Transaction logged.")
                
            except Exception as e:
                # 2. THE RATE LIMIT CATCH: If Groq rejects the request before the math updates
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    # Force the tokens to max and start the 60 second timer immediately
                    st.session_state.session_tokens = GROQ_TPM_LIMIT
                    st.session_state.last_run_time = time.time()
                    draw_sidebar_tracker() # Instantly turn the sidebar red
                    
                    st.error("❌ Groq API Rate Limit Hit! You have exhausted your free tier tokens. Please wait exactly 60 seconds and try again.")
                else:
                    st.error(f"An execution error occurred in the state machine: {str(e)}")