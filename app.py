import streamlit as st
import os
import json

# --- 1. Streamlit Page Setup ---
st.set_page_config(
    page_title="LexAudit-Zero", 
    page_icon="⚖️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. Sidebar for API Keys (Securing your colleagues) ---
with st.sidebar:
    st.header("⚙️ System Configuration")
    st.markdown("Enter your API keys to initialize the audit engine. *Keys are not stored.*")
    
    # We use type="password" so keys are masked on the screen
    groq_key = st.text_input("Groq API Key (For Llama 3.3)", type="password")
    tavily_key = st.text_input("Tavily API Key (For Legal Search)", type="password")
    
    st.markdown("---")
    st.markdown("### 📚 About LexAudit-Zero")
    st.markdown("This tool audits Offer Letters and HR Policies against the Indian Labour Codes (2026).")
    st.markdown("**Architecture:** Corrective RAG (CRAG)")
    st.markdown("*(Maintained as an open-source rebellion utility)*")

# --- 3. Main UI ---
st.title("⚖️ LexAudit-Zero: Compliance Engine")
st.markdown("Identify non-compliant corporate clauses, illegal bonds, and labor law violations.")

# We only load the engine IF keys are provided to prevent LangChain from crashing on import
if not groq_key or not tavily_key:
    st.info("👈 Please enter both Groq and Tavily API keys in the sidebar to begin.")
else:
    # Set environment variables so LangChain/LangGraph can pick them up dynamically
    os.environ["GROQ_API_KEY"] = groq_key
    os.environ["TAVILY_API_KEY"] = tavily_key
    
    # Import the graph ONLY after keys are set in the environment
    try:
        from agent_engine import app as crag_app
        st.success("✅ Audit Engine Online. FAISS Vector Store Connected.")
    except Exception as e:
        st.error(f"Failed to initialize the engine. Ensure 'faiss_legal_db' exists in this directory. Error: {e}")
        st.stop()

    # --- 4. Query Input ---
    user_query = st.text_area(
        "Enter the clause or policy rule you want to audit:",
        placeholder="e.g., 'The employee must serve a 90-day notice period, but the company reserves the right to terminate employment with 15 days notice.'",
        height=100
    )

    if st.button("Run Compliance Audit", type="primary"):
        if not user_query:
            st.error("Please enter a clause or question to audit.")
        else:
            # st.status gives us a cool expanding loading box to show the CRAG steps
            with st.status("Initiating CRAG Pipeline...", expanded=True) as status:
                inputs = {"question": user_query}
                final_report = ""
                
                # Stream the LangGraph execution steps live to the UI
                for output in crag_app.stream(inputs):
                    for node_name, node_state in output.items():
                        if node_name == "retrieve":
                            st.write("🔍 **Step 1:** Retrieving local policy documents from FAISS...")
                        
                        elif node_name == "grade_documents":
                            score = node_state.get("generation", "NO")
                            if score == "YES":
                                st.write("✅ **Step 2:** Grader determined local documents are sufficient.")
                            else:
                                st.write("⚠️ **Step 2:** Local documents insufficient or ambiguous. Triggering Legal Web Search Fallback.")
                        
                        elif node_name == "web_search":
                            st.write("🌐 **Step 3:** Executing external Tavily Search for Indian Labor Codes...")
                        
                        elif node_name == "generate_audit":
                            st.write("📝 **Step 4:** Synthesizing legal audit report...")
                            final_report = node_state.get("generation", "")
                
                # Close the status box once done
                status.update(label="Audit Complete!", state="complete", expanded=False)

            # --- 4.5 Auto-Logging to .DONT_UPLOAD/track.json ---
            # Automatically save the prompt and response, incrementing the execution number
            log_dir = ".DONT_UPLOAD"
            log_file = os.path.join(log_dir, "track.json")
            
            # Ensure the directory exists
            os.makedirs(log_dir, exist_ok=True)
            
            # Read existing logs to determine the next execution number
            existing_logs = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        existing_logs = json.load(f)
                        if isinstance(existing_logs, dict): # Handle if it was manually saved as a single dict
                            existing_logs = [existing_logs]
                except json.JSONDecodeError:
                    existing_logs = []
            
            next_exec = 1 if not existing_logs else max([log.get("execution_number", 0) for log in existing_logs]) + 1
            
            # Append new log
            existing_logs.append({
                "execution_number": next_exec,
                "data": {
                    "Prompt": user_query,
                    "Response": final_report
                }
            })
            
            # Write back to file
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(existing_logs, f, indent=4)

            # --- 5. Display the Final Report ---
            st.markdown("---")
            st.subheader("📑 Audit Findings")
            
            # Render the Markdown response directly
            st.markdown(final_report)