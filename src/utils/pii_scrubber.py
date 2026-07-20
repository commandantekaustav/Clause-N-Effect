import re
import os
from langchain_groq import ChatGroq
from pydantic import SecretStr

def scrub_pii(text: str) -> str:
    # 1. Regex Scrub
    text = re.sub(r'\S+@\S+', '[EMAIL]', text)
    text = re.sub(r'\+?\d{10,12}', '[PHONE]', text)
    text = re.sub(r'http\S+|www\S+', '[URL]', text)

    # 2. LLM Scrub
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return text # Return regex-scrubbed text if no key
        
    llm = ChatGroq(
        model="llama-3.1-8b-instant", 
        temperature=0, 
        # FIX: Ensure key is a string, not None
        api_key=SecretStr(key) 
    )
    
    sanitizer_prompt = f"""
    SYSTEM: You are a silent redaction engine. 
    TASK: Replace all Names, Companies, and Locations with [PERSON], [COMPANY], or [LOCATION].
    
    STRICT RULES:
    1. OUTPUT ONLY THE REDACTED TEXT. 
    2. DO NOT include "Here is the text" or any conversational filler.
    3. If the input is incomplete, REDACT WHAT IS THERE. DO NOT ASK QUESTIONS.
    
    TEXT:
    {text}
    """
    
    try:
        response = llm.invoke(sanitizer_prompt)
        # Clean up any potential conversational leaks
        cleaned = str(response.content).strip()
        # If the model still adds "Here is the redacted text:", we strip it
        cleaned = re.sub(r"^(Here is|The following is|Redacted text).*?:", "", cleaned, flags=re.IGNORECASE|re.DOTALL)
        return cleaned.strip()
    except Exception:
        return text