import re

def crush_corporate_noise(raw_text: str) -> str:
    """
    Zero-cost preprocessing to strip repetitive corporate email bloat 
    before it hits the LLM context window.
    """
    # 1. Strip repetitive disclaimers
    disclaimers = [
        r"The information contained in this email and any attachments is confidential.*?(?:mail system\.)",
        r"No\. 12, Lakshmi Nagar, Thottipalayam Pirivu.*?Website: www\.faceprep(?:campus)?\.in"
    ]
    for pattern in disclaimers:
        raw_text = re.sub(pattern, "", raw_text, flags=re.IGNORECASE | re.DOTALL)
        
    # 2. Strip the massive Escalation Matrix table
    matrix_pattern = r"Kindly take note of the updated Escalation Matrix.*?Nazma Nijamji Vice President \(Talent Management\) \d{10} [^\s]+"
    raw_text = re.sub(matrix_pattern, "[SYSTEM: ESCALATION MATRIX REMOVED FOR BREVITY]", raw_text, flags=re.IGNORECASE | re.DOTALL)
    
    # 3. Clean up excessive blank lines created by the removal
    raw_text = re.sub(r'\n{3,}', '\n\n', raw_text)
    
    return raw_text.strip()