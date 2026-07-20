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
    REDACTION TASK:
    Replace all Names of people, Company Names, and specific Office Locations in the text below with generic placeholders like [PERSON], [COMPANY], or [LOCATION].
    LEAVE INTACT: Dates, timestamps, job titles, and statutory terms.
    
    TEXT:
    {text}
    """
    
    try:
        response = llm.invoke(sanitizer_prompt)
        return str(response.content)
    except Exception:
        return text