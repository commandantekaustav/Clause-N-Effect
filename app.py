import os
import time
import streamlit as st
from agent_engine import app as crag_app
from logger import log_transaction
from src.utils.stream_handler import execute_and_stream_graph

import dotenv
dotenv.load_dotenv()

st.set_page_config(
    page_title="Clause-N-Effect: Legal Sidekick for Gen-Z",
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
st.markdown("From [Kaustav](https://commandantekaustav.github.io), with Love! ;) ", text_alignment="left")

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
        if time.time() - st.session_state.last_run_time > 60:
            st.session_state.session_tokens = 0
            
        usage_percent = min(st.session_state.session_tokens / GROQ_TPM_LIMIT, 1.0)
        
        with sidebar_tracker.container():
            st.progress(usage_percent)
            st.caption(f"**Groq TPM Usage (approx):** {int(st.session_state.session_tokens)} / {GROQ_TPM_LIMIT}")
            
            if usage_percent >= 1.0:
                st.error("❌ Rate Limit Hit (Wait 60s)")
            elif usage_percent > 0.8:
                st.warning("⚠️ Approaching Free Tier limit!")
            else:
                st.success("✅ API Status: Healthy")

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
    tokens = int(len(text) / 4) 
    
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
# MAIN UI LAYOUT
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

            try:
                with status_placeholder.status("Executing Actor-Critic Routing Nodes...", expanded=True) as status:
                    
                    # --- THE CLEAN ABSTRACTION ---
                    # Create the empty UI box for the terminal
                    terminal_box = st.empty()
                    
                    # Call the backend function and pass the UI components to it
                    final_generation, final_steps, safe_query, safe_facts, revisions, rejection_reasons, execution_latency = execute_and_stream_graph(
                        crag_app=crag_app,
                        inputs=inputs,
                        terminal_box=terminal_box,
                        input_tokens=input_tokens,
                        update_tracker_callback=draw_sidebar_tracker,
                        
                    )
                    # -----------------------------
                    
                    status.update(label="Audit Completed!", state="complete", expanded=False)
                
                # Update run time and display results
                st.session_state.last_run_time = time.time()
                
                # --- VISUAL CLASSIFICATION PARSER ---
                # Check for the tags using upper() to ensure case-insensitivity
                gen_upper = final_generation.upper()
                
                # UI Layer Styling: Colorize the blockquotes dynamically
                if "[NON-COMPLIANT]" in gen_upper or "[LEGALLY VOID]" in gen_upper:
                    # Make blockquotes red for violations
                    display_text = final_generation.replace("\n> ", "\n> <span style='color:#ff4b4b; font-weight:bold'>")
                    display_text = display_text.replace('"\n', '"</span>\n')
                else:
                    # Make blockquotes green for compliance
                    display_text = final_generation.replace("\n> ", "\n> <span style='color:#00cc66; font-weight:bold'>")
                    display_text = display_text.replace('"\n', '"</span>\n')
                
                st.markdown(display_text, unsafe_allow_html=True)
                                
                log_transaction(
                    query=safe_query,
                    hr_facts=safe_facts,
                    response=final_generation,
                    steps=final_steps,
                    execution_time=execution_latency,
                    revision_count=revisions,
                    rejection_reasons=rejection_reasons # <--- Pass it here
                )
                
                st.toast(f"Audit completed in {execution_latency:.2f}s. Transaction logged.")
                
            except Exception as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    st.session_state.session_tokens = GROQ_TPM_LIMIT
                    st.session_state.last_run_time = time.time()
                    draw_sidebar_tracker() 
                    st.error("❌ Groq API Rate Limit Hit! You have exhausted your free tier tokens. Please wait exactly 60 seconds and try again.")
                else:
                    st.error(f"An execution error occurred in the state machine: {str(e)}")

# ==========================================
# THE MANIFESTO & FOOTNOTE
# ==========================================
st.markdown("---")
with st.expander("About Clause-N-Effect | The Manifesto & Architecture"):
        st.markdown("""
        **The Purpose**
        Information asymmetry is the oldest negotiation tactic in the corporate playbook. This tool exists to close that gap. Clause-N-Effect is an open-source educational utility designed to promote statutory awareness and strict organizational transparency. It translates internal HR jargon into bare legal realities, ensuring that "standard procedures" are actually statutory, and "mutual agreements" are genuinely mutual. 

        **How to Use It**
        1. Sanitize your data. Strip out your personal identifiable information (PII) if you prefer, but keep the professional metadata (To, Cc, Bcc, timestamps) intact.
        2. Paste the exact verbatim text of the email chain, contract clause, or communication.
        3. State your query clearly.
        4. Let the state machine investigate.

        **The Architecture**
        This is not a standard generative wrapper. Clause-N-Effect operates on a deterministic LangGraph state machine utilizing Hybrid-Brain orchestration. It deploys a localized 8B parameter model for rapid forensic metadata extraction, query compression, and targeted web scraping. It reserves a 70B parameter model exclusively for deep statutory reasoning and compliance benchmarking. 
        
        The pipeline relies on a self-correcting Actor-Critic loop. The system deploys an internal 'Judge' that ruthlessly evaluates the AI's own audit against Indian Labor Codes. If the logic or evidence citation fails, the Judge forces the generator into a rewrite loop before the output ever reaches your screen.

        **The Roadmap**
        V1.0 is currently calibrated to intercept Unfair Labor Practices, Specific Relief Act violations (forced labor/resignation denial), and coercive metadata signatures (defensive paper trails). 
        V2.0 is in active development. The roadmap includes BM25 Sparse Search integration for exact-keyword legal precedent retrieval, and GraphRAG (Knowledge Graphs) to mathematically map corporate hierarchies and toxic power dynamics.

        **Legal Disclaimer**
        This application does not provide formal legal counsel. It is a strictly educational framework built to help both individuals and organizations maintain rigorous alignment with the Industrial Disputes Act, 1947, the Indian Contract Act, 1872, and various State-specific mandates. Strict compliance protects everyone.

        **To the incoming workforce:** 
        Knowledge is leverage. Document your interactions, understand the actual definitions of your contracts, and never allow professional courtesy to be weaponized into blind compliance. You are the talent; protect your boundaries. 

        Feedback, architecture discussions, or edge-case reports can be directed to: commandantek@protonmail.com.

        In solidarity.
        """)