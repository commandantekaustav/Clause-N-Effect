import os
import time
import streamlit as st
from agent_engine import app as crag_app
from logger import log_transaction

import dotenv
dotenv.load_dotenv()  # Load environment variables from .env file

st.set_page_config(
    page_title="Clause-N-Effect: Legal Compliance Auditor",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Clause-N-Effect")
st.subheader("Agentic Legal Compliance Auditor (CRAG) - Actor-Critic Architecture")

with st.sidebar:
    st.header("Configuration")
    groq_api_key = st.text_input("Groq API Key", type="password")
    tavily_api_key = st.text_input("Tavily API Key", type="password")
    
    st.markdown("---")
    st.markdown("### Telemetry Status")
    if os.path.exists(".DONT_UPLOAD/track.json"):
        st.success("Telemetry Active: Logging to `.DONT_UPLOAD/track.json`")
    else:
        st.info("No logs captured yet. Run an audit to generate telemetry.")

col1, col2 = st.columns(2)

with col1:
    employer_facts = st.text_area(
        "1. Paste the Employer Clause / Email:",
        placeholder="e.g., 'Original certificates will be held for 3 years...' or paste the HR email here.",
        height=200
    )

with col2:
    user_query = st.text_area(
        "2. What is your legal query?",
        placeholder="e.g., Is this legal? How do I get my marksheet back?",
        height=200
    )

if st.button("Run Compliance Audit", type="primary"):
    if not groq_api_key or not tavily_api_key:
        st.error("Please provide both Groq and Tavily API keys in the sidebar.")
    elif not user_query.strip() or not employer_facts.strip():
        st.warning("Please fill out both the employer facts and your specific query.")
    else:
        os.environ["GROQ_API_KEY"] = groq_api_key
        os.environ["TAVILY_API_KEY"] = tavily_api_key
        
        status_placeholder = st.empty()
        
        combined_payload = f"USER QUERY: {user_query.strip()}\n\nTARGET HR FACTS:\n{employer_facts.strip()}"
        
        # Inject initialization for the cyclic routing mechanics
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
                        
                        # Render Red Team Defense Live
                        if "corporate_defense" in state_delta and state_delta["corporate_defense"]:
                            with st.expander("Corporate HR Defense Generated"):
                                st.write(state_delta["corporate_defense"])
                                
                        # Render Judge Criticisms Live
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
            
            st.markdown("### Compliance Audit Report")
            st.markdown(final_generation, unsafe_allow_html=True)
            
            log_transaction(
                query=distilled_query,
                response=final_generation,
                steps=final_steps,
                execution_time=execution_latency
            )
            
            st.toast(f"Audit completed in {execution_latency:.2f}s. Transaction logged.")
            
        except Exception as e:
            st.error(f"An execution error occurred in the state machine: {str(e)}")

if __name__ == "__main__":
    st.info("This Streamlit app is designed to run the Clause-N-Effect compliance audit. Please provide the necessary inputs and API keys in the sidebar.")
    groq_api_key = os.getenv("GROQ_API_KEY")
    tavily_api_key = os.getenv("TAVILY_API_KEY")